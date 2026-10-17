from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import threading
import unicodedata
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from prediction.predictor import PricePredictor
from prediction.training import sha256_file


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_ARTIFACT_ROOT = PROJECT_DIR / "artifacts"
MAX_REQUEST_BYTES = 16 * 1024


class RequestValidationError(ValueError):
    pass


class StaleModelError(RequestValidationError):
    pass


@dataclass(frozen=True)
class ArtifactSettings:
    artifact_dir: Path


def normalized_search_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).upper().strip()
    return "".join(character for character in text if character.isalnum())


def suggestion_id(model_name: str) -> str:
    normalized = normalized_search_text(model_name)
    return hashlib.sha256(f"model:{normalized}".encode("utf-8")).hexdigest()[:20]


def validate_year(value: Any) -> int:
    try:
        year = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise RequestValidationError("연식을 숫자로 입력해주세요.") from error
    if str(value).strip() not in {str(year), f"{year}.0"}:
        raise RequestValidationError("연식은 정수여야 합니다.")
    if not 1970 <= year <= dt.date.today().year + 1:
        raise RequestValidationError("연식이 허용 범위를 벗어났습니다.")
    return year


def _optional_number(value: Any, *, minimum: float, maximum: float, label: str) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise RequestValidationError(f"{label} 값이 올바르지 않습니다.") from error
    if not minimum <= number <= maximum:
        raise RequestValidationError(f"{label} 값이 허용 범위를 벗어났습니다.")
    return number


class PredictionRuntime:
    def __init__(self, artifact_root: Path):
        self.settings = ArtifactSettings(Path(artifact_root).expanduser().resolve())
        self._lock = threading.RLock()
        self._latest_signature: Optional[tuple[int, int]] = None
        self.predictor: Optional[PricePredictor] = None
        self.models: list[dict[str, Any]] = []
        self.models_by_id: dict[str, dict[str, Any]] = {}
        self.models_by_name: dict[str, dict[str, Any]] = {}
        self.model_version = ""
        self.trained_at = ""

    @property
    def latest_path(self) -> Path:
        return self.settings.artifact_dir / "price" / "latest.json"

    def _signature(self) -> tuple[int, int]:
        stat = self.latest_path.stat()
        return stat.st_mtime_ns, stat.st_size

    def ensure_loaded(self) -> None:
        signature = self._signature()
        if self.predictor is not None and signature == self._latest_signature:
            return
        with self._lock:
            signature = self._signature()
            if self.predictor is not None and signature == self._latest_signature:
                return
            predictor = PricePredictor(self.settings)
            suggestions_name = str(predictor.manifest.get("model_suggestions") or "")
            if not suggestions_name:
                raise RuntimeError("trained artifact has no model suggestions")
            suggestions_path = (predictor.artifact_dir / suggestions_name).resolve()
            if predictor.artifact_dir not in suggestions_path.parents or not suggestions_path.is_file():
                raise RuntimeError("invalid model suggestions artifact")
            expected_checksum = (predictor.manifest.get("artifact_sha256") or {}).get(suggestions_name)
            if not expected_checksum or sha256_file(suggestions_path) != expected_checksum:
                raise RuntimeError("model suggestions checksum mismatch")
            payload = json.loads(suggestions_path.read_text(encoding="utf-8"))
            if payload.get("format_version") != 1 or not isinstance(payload.get("models"), list):
                raise RuntimeError("unsupported model suggestions format")

            models = []
            for raw in payload["models"]:
                if not isinstance(raw, dict):
                    raise RuntimeError("invalid model suggestion entry")
                model_name = str(raw.get("model_name") or "").strip()
                if not model_name:
                    continue
                item = {
                    "id": suggestion_id(model_name),
                    "modelName": model_name,
                    "categoryName": raw.get("category_name"),
                    "categoryCode": raw.get("category_code"),
                    "manufacturer": raw.get("manufacturer"),
                    "sampleCount": int(raw.get("sample_count") or 0),
                    "yearMin": raw.get("year_min"),
                    "yearMax": raw.get("year_max"),
                    "_features": {
                        "category_name": raw.get("category_name"),
                        "category_code": raw.get("category_code"),
                        "manufacturer": raw.get("manufacturer"),
                        "equipment_status": raw.get("equipment_status"),
                        "source_site": raw.get("source_site"),
                        "location": raw.get("location"),
                    },
                }
                models.append(item)

            self.predictor = predictor
            self.models = models
            self.models_by_id = {item["id"]: item for item in models}
            self.models_by_name = {
                normalized_search_text(item["modelName"]): item for item in models
            }
            self.model_version = predictor.artifact_dir.name
            self.trained_at = str(predictor.manifest.get("trained_at") or "")
            self._latest_signature = signature

    def public_model(self, item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if not key.startswith("_")}

    def suggestion_snapshot(self, query: str, limit: int) -> dict[str, Any]:
        with self._lock:
            self.ensure_loaded()
            normalized = normalized_search_text(query)
            ranked = []
            for item in self.models:
                candidate = normalized_search_text(item["modelName"])
                if normalized and normalized not in candidate:
                    continue
                rank = 0 if candidate == normalized else 1 if candidate.startswith(normalized) else 2
                ranked.append((rank, -int(item["sampleCount"]), item["modelName"], item))
            ranked.sort(key=lambda value: value[:3])
            return {
                "modelVersion": self.model_version,
                "items": [self.public_model(value[3]) for value in ranked[:limit]],
            }

    def suggestions(self, query: str, limit: int) -> list[dict[str, Any]]:
        return self.suggestion_snapshot(query, limit)["items"]

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            # Keep the selected suggestion metadata and estimator on the same
            # artifact generation while latest.json is being hot-reloaded.
            self.ensure_loaded()
            requested_version = str(payload.get("modelVersion") or "").strip()
            if requested_version and requested_version != self.model_version:
                raise StaleModelError(
                    "가격 모델이 업데이트되었습니다. 모델을 다시 검색해 선택해주세요."
                )
            model_id = str(payload.get("suggestionId") or "").strip()
            model_name = str(payload.get("modelName") or "").strip()
            selected = self.models_by_id.get(model_id) if model_id else None
            if selected is None and model_name:
                selected = self.models_by_name.get(normalized_search_text(model_name))
            if selected is None:
                raise RequestValidationError("제안 목록에서 모델을 선택해주세요.")
            year = validate_year(payload.get("manufacturedYear"))
            month = _optional_number(
                payload.get("manufacturedMonth"), minimum=1, maximum=12, label="제작월"
            )
            if month is not None and not month.is_integer():
                raise RequestValidationError("제작월은 정수여야 합니다.")
            hours = _optional_number(
                payload.get("operatingHours"), minimum=0, maximum=200_000, label="가동시간"
            )
            features = {
                "model_norm": selected["modelName"],
                "manufactured_year": year,
                "manufactured_month": int(month) if month is not None else None,
                "operating_hours": hours,
                "posted_at": dt.datetime.now(),
                **selected["_features"],
            }
            result = self.predictor.predict_one(**features)  # type: ignore[union-attr]
            predicted_price = int(result["predicted_price_krw"])
            web_metrics = (
                self.predictor.manifest.get("metrics", {})  # type: ignore[union-attr]
                .get(result["algorithm"], {})
            )
            api_metrics = web_metrics.get("api_serving_test") or web_metrics.get(
                "web_serving_test", {}
            )
            web_mae = float(api_metrics.get("mae_krw") or 0.0)
            if web_mae > 0:
                expected_low = max(0, int(round(predicted_price - web_mae)))
                expected_high = int(round(predicted_price + web_mae))
                range_metric = "api_serving_test_mae"
                range_notice = (
                    "API에서 선택 가능한 모델의 모델명·연식 테스트 MAE를 가감한 "
                    "참고 범위이며 "
                    "통계적 신뢰구간이 아닙니다."
                )
            else:
                expected_low = int(result["expected_low_krw"])
                expected_high = int(result["expected_high_krw"])
                range_metric = "test_mae"
                range_notice = (
                    "테스트 MAE를 가감한 참고 범위이며 통계적 신뢰구간이 아닙니다."
                )
            sample_count = int(selected.get("sampleCount") or 0)
            year_min = selected.get("yearMin")
            year_max = selected.get("yearMax")
            extrapolated = bool(
                year_min is not None
                and year_max is not None
                and (year < int(year_min) or year > int(year_max))
            )
            notices = [range_notice]
            if sample_count < 5:
                notices.append(
                    "이 모델은 학습 표본이 5건 미만이어서 제조사·카테고리 평균의 영향을 "
                    "크게 받습니다."
                )
            if extrapolated:
                notices.append(
                    f"입력 연식이 학습 관측 범위({year_min}~{year_max}년) 밖이므로 "
                    "외삽 오차가 커질 수 있습니다."
                )
            return {
                "predictedPriceKrw": predicted_price,
                "expectedLowKrw": expected_low,
                "expectedHighKrw": expected_high,
                "algorithm": result["algorithm"],
                "modelVersion": self.model_version,
                "trainedAt": self.trained_at,
                "input": {
                    "modelName": selected["modelName"],
                    "manufacturedYear": year,
                    "manufacturedMonth": int(month) if month is not None else None,
                    "operatingHours": hours,
                    "categoryName": selected.get("categoryName"),
                    "categoryCode": selected.get("categoryCode"),
                    "manufacturer": selected.get("manufacturer"),
                    "sampleCount": selected.get("sampleCount"),
                },
                "rangeMetric": range_metric,
                "rangeNotice": " ".join(notices),
                "extrapolated": extrapolated,
                "reliability": "low" if sample_count < 5 or extrapolated else "standard",
            }


class PredictionHandler(BaseHTTPRequestHandler):
    runtime: PredictionRuntime
    server_version = "HeavyEquipPrediction/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/health":
                self.runtime.ensure_loaded()
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, "modelVersion": self.runtime.model_version},
                )
                return
            if parsed.path == "/models":
                query = str((parse_qs(parsed.query).get("q") or [""])[0])[:100]
                raw_limit = str((parse_qs(parsed.query).get("limit") or ["12"])[0])
                try:
                    limit = min(max(int(raw_limit), 1), 20)
                except ValueError:
                    limit = 12
                self._json(
                    HTTPStatus.OK,
                    self.runtime.suggestion_snapshot(query, limit),
                )
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except (OSError, KeyError, TypeError, RuntimeError, ValueError):
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "prediction_unavailable"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if urlparse(self.path).path != "/predict":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("content-length") or 0)
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise RequestValidationError("요청 크기가 올바르지 않습니다.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise RequestValidationError("JSON 객체가 필요합니다.")
            self._json(HTTPStatus.OK, self.runtime.predict(payload))
        except StaleModelError as error:
            self._json(HTTPStatus.CONFLICT, {"error": str(error)})
        except RequestValidationError as error:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "JSON 형식이 올바르지 않습니다."})
        except (OSError, KeyError, TypeError, RuntimeError, ValueError):
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "prediction_unavailable"})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[prediction-api] {self.address_string()} {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local price prediction API")
    parser.add_argument("--host", default=os.environ.get("PREDICTION_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PREDICTION_API_PORT", "5060")))
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path(os.environ.get("PREDICTION_ARTIFACT_ROOT", DEFAULT_ARTIFACT_ROOT)),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    PredictionHandler.runtime = PredictionRuntime(args.artifact_root)
    PredictionHandler.runtime.ensure_loaded()
    server = ThreadingHTTPServer((args.host, args.port), PredictionHandler)
    print(
        f"[prediction-api] listening http://{args.host}:{args.port} "
        f"model={PredictionHandler.runtime.model_version}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
