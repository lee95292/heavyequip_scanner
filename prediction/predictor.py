from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from prediction.config import PredictionSettings
from prediction.training import (
    FEATURE_COLUMNS,
    package_version,
    prepare_feature_frame,
    sha256_file,
)


def _version_prefix(value: str, parts: int) -> tuple[int, ...]:
    numbers = []
    for segment in str(value).split("."):
        digits = "".join(character for character in segment if character.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
        if len(numbers) == parts:
            break
    return tuple(numbers)


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("format_version") != 1:
        raise ValueError(f"unsupported artifact format_version: {manifest.get('format_version')!r}")
    if manifest.get("features") != list(FEATURE_COLUMNS):
        raise ValueError("artifact feature schema is incompatible with this prediction code")
    if manifest.get("target") != "log1p(price_krw)":
        raise ValueError("artifact target transform is incompatible with this prediction code")

    trained_versions = manifest.get("versions") or {}
    compatibility_parts = {
        "python": 1,
        "numpy": 1,
        "scipy": 1,
        "scikit-learn": 2,
        "joblib": 1,
    }
    for package, parts in compatibility_parts.items():
        trained = str(trained_versions.get(package) or "")
        runtime = package_version(package)
        if not trained or _version_prefix(trained, parts) != _version_prefix(runtime, parts):
            raise RuntimeError(
                f"artifact {package} version is incompatible: trained={trained or 'missing'}, "
                f"runtime={runtime}"
            )


def validate_prediction_frame(frame: pd.DataFrame) -> None:
    required = {"model_norm", "manufactured_year"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"prediction input is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("prediction input has no rows")

    model_names = frame["model_norm"].fillna("").astype(str).str.strip()
    if model_names.eq("").any():
        raise ValueError(
            f"prediction input has {int(model_names.eq('').sum())} rows with an empty model_norm"
        )

    years = pd.to_numeric(frame["manufactured_year"], errors="coerce")
    max_year = dt.date.today().year + 1
    invalid_years = years.isna() | ~years.between(1970, max_year) | (years % 1 != 0)
    if invalid_years.any():
        raise ValueError(
            f"prediction input has {int(invalid_years.sum())} rows with an invalid manufactured_year"
        )

    for column, minimum, maximum in (
        ("manufactured_month", 1, 12),
        ("operating_hours", 0, 200_000),
    ):
        if column not in frame:
            continue
        raw = frame[column]
        present = raw.notna() & raw.astype(str).str.strip().ne("")
        numeric = pd.to_numeric(raw, errors="coerce")
        invalid = present & (numeric.isna() | ~numeric.between(minimum, maximum))
        if column == "manufactured_month":
            invalid |= present & (numeric % 1 != 0)
        if invalid.any():
            raise ValueError(
                f"prediction input has {int(invalid.sum())} rows with an invalid {column}"
            )


def _verify_checksum(path: Path, expected: Optional[str]) -> None:
    if expected and sha256_file(path) != expected:
        raise ValueError(f"artifact checksum mismatch: {path.name}")


def _artifact_file(artifact_dir: Path, relative_name: str) -> Path:
    path = (artifact_dir / relative_name).resolve()
    if artifact_dir != path and artifact_dir not in path.parents:
        raise ValueError(f"artifact file escapes artifact directory: {relative_name}")
    if not path.is_file():
        raise FileNotFoundError(f"artifact file not found: {path}")
    return path


def resolve_artifact_dir(settings: PredictionSettings, artifact_dir: Optional[Path] = None) -> Path:
    expected_manifest_checksum: Optional[str] = None
    if artifact_dir is not None:
        result = Path(artifact_dir).expanduser().resolve()
    else:
        latest_path = settings.artifact_dir / "price" / "latest.json"
        if not latest_path.exists():
            raise FileNotFoundError("no trained price model found; run `python -m prediction train`")
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        result = Path(latest["artifact_dir"]).expanduser().resolve()
        expected_manifest_checksum = latest.get("manifest_sha256")
        if not expected_manifest_checksum:
            raise ValueError("latest artifact pointer has no manifest checksum")
    manifest_path = result / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"invalid price model artifact: {result}")
    _verify_checksum(manifest_path, expected_manifest_checksum)
    return result


class PricePredictor:
    def __init__(
        self,
        settings: PredictionSettings,
        *,
        artifact_dir: Optional[Path] = None,
        algorithm: Optional[str] = None,
    ):
        self.artifact_dir = resolve_artifact_dir(settings, artifact_dir)
        self.manifest = json.loads((self.artifact_dir / "manifest.json").read_text(encoding="utf-8"))
        validate_manifest(self.manifest)
        self.algorithm = str(algorithm or self.manifest["best_model"]).lower()
        model_files = self.manifest.get("models") or {}
        if self.algorithm not in model_files:
            raise ValueError(
                f"algorithm {self.algorithm!r} is not in artifact; available={sorted(model_files)}"
            )
        checksums = self.manifest.get("artifact_sha256") or {}
        preprocessor_path = _artifact_file(self.artifact_dir, self.manifest["preprocessor"])
        preprocessor_checksum = checksums.get(self.manifest["preprocessor"])
        model_checksum = checksums.get(model_files[self.algorithm])
        if not preprocessor_checksum or not model_checksum:
            raise ValueError("artifact manifest is missing required file checksums")
        _verify_checksum(preprocessor_path, preprocessor_checksum)
        self.preprocessor = joblib.load(preprocessor_path)
        model_path = _artifact_file(self.artifact_dir, model_files[self.algorithm])
        _verify_checksum(model_path, model_checksum)
        if self.algorithm == "xgboost":
            from xgboost import XGBRegressor

            self.model = XGBRegressor()
            self.model.load_model(model_path)
        elif self.algorithm == "lightgbm":
            import lightgbm as lgb

            self.model = lgb.Booster(model_file=str(model_path))
        else:
            raise ValueError(f"unsupported algorithm: {self.algorithm}")

    def predict_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        validate_prediction_frame(frame)
        transformed = self.preprocessor.transform(prepare_feature_frame(frame))
        log_predictions = np.asarray(self.model.predict(transformed), dtype=float)
        predictions = np.maximum(0.0, np.expm1(log_predictions))
        mae = float(
            self.manifest.get("metrics", {})
            .get(self.algorithm, {})
            .get("test", {})
            .get("mae_krw", 0.0)
        )
        result = frame.copy()
        result["predicted_price_krw"] = np.rint(predictions).astype(np.int64)
        # This is an empirical MAE band, not a calibrated statistical interval.
        result["expected_low_krw"] = np.rint(np.maximum(0.0, predictions - mae)).astype(np.int64)
        result["expected_high_krw"] = np.rint(predictions + mae).astype(np.int64)
        result["prediction_model"] = self.algorithm
        return result

    def predict_one(self, **features: Any) -> dict[str, Any]:
        result = self.predict_frame(pd.DataFrame([features])).iloc[0]
        return {
            "predicted_price_krw": int(result["predicted_price_krw"]),
            "expected_low_krw": int(result["expected_low_krw"]),
            "expected_high_krw": int(result["expected_high_krw"]),
            "algorithm": self.algorithm,
            "artifact_dir": str(self.artifact_dir),
        }


def predict_csv(
    predictor: PricePredictor,
    input_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    source = Path(input_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    frame = pd.read_csv(source)
    validate_prediction_frame(frame)
    predicted = predictor.predict_frame(frame)
    output.parent.mkdir(parents=True, exist_ok=True)
    predicted.to_csv(output, index=False, encoding="utf-8-sig")
    return {"input_path": str(source), "output_path": str(output), "rows": len(predicted)}
