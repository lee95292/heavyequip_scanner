from __future__ import annotations

import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import HuberRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from prediction.config import PredictionSettings
from prediction.model_name import normalize_model_name
from prediction.warehouse import WarehouseRepository


NUMERIC_FEATURES = (
    "manufactured_year",
    "manufactured_month",
    "manufactured_month_missing",
    "equipment_age",
    "operating_hours_log",
    "operating_hours_missing",
    "reference_date_missing",
)
MODEL_FEATURE = "model_norm"
CATEGORICAL_FEATURES = (
    MODEL_FEATURE,
    "manufacturer",
    "category_code",
    "category_name",
    "equipment_status",
    "source_site",
    "location",
)
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES
SUGGESTION_CONTEXT_FEATURES = (
    "manufacturer",
    "category_code",
    "category_name",
    "equipment_status",
    "source_site",
    "location",
)


def package_version(name: str) -> str:
    if name == "python":
        return platform.python_version()
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        destination.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def promote_artifact(settings: PredictionSettings, artifact_dir: Path) -> Path:
    bundle = Path(artifact_dir).expanduser().resolve()
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"artifact manifest not found: {manifest_path}")
    latest = settings.artifact_dir / "price" / "latest.json"
    write_json_atomic(
        latest,
        {
            "artifact_dir": str(bundle),
            "manifest_sha256": sha256_file(manifest_path),
        },
    )
    return latest


def code_revision() -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--", "prediction"],
                cwd=repository_root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        return {"git_commit": commit, "git_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": "unknown", "git_dirty": None}


def _context_text(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _dominant_context(group: pd.DataFrame) -> tuple[Optional[str], ...]:
    counts: dict[tuple[Optional[str], ...], int] = {}
    for row in group.reindex(columns=SUGGESTION_CONTEXT_FEATURES).itertuples(
        index=False,
        name=None,
    ):
        context = tuple(_context_text(value) for value in row)
        counts[context] = counts.get(context, 0) + 1
    if not counts:
        return tuple(None for _ in SUGGESTION_CONTEXT_FEATURES)
    return min(
        counts,
        key=lambda context: (
            -counts[context],
            tuple(value or "" for value in context),
        ),
    )


def build_model_suggestions(frame: pd.DataFrame) -> dict[str, Any]:
    if MODEL_FEATURE not in frame:
        return {"format_version": 1, "models": []}
    working = frame.copy()
    working[MODEL_FEATURE] = working[MODEL_FEATURE].fillna("").astype(str).str.strip()
    working = working[working[MODEL_FEATURE].ne("")]
    models = []
    for model_name, group in working.groupby(MODEL_FEATURE, sort=True):
        year_source = (
            group["manufactured_year"]
            if "manufactured_year" in group
            else pd.Series(index=group.index, dtype=float)
        )
        years = pd.to_numeric(year_source, errors="coerce").dropna()
        context = _dominant_context(group)
        entry: dict[str, Any] = {
            "model_name": str(model_name),
            "sample_count": int(len(group)),
            "year_min": int(years.min()) if not years.empty else None,
            "year_max": int(years.max()) if not years.empty else None,
        }
        for column, value in zip(SUGGESTION_CONTEXT_FEATURES, context):
            entry[column] = value
        models.append(entry)
    return {"format_version": 1, "models": models}


def prepare_web_serving_frame(
    frame: pd.DataFrame,
    suggestions: dict[str, Any],
) -> pd.DataFrame:
    """Mirror the dashboard's model-name + year-only inference inputs."""
    result = frame.copy()
    context_by_model = {
        str(item.get("model_name") or "").strip(): item
        for item in suggestions.get("models", [])
        if isinstance(item, dict) and str(item.get("model_name") or "").strip()
    }
    model_names = result[MODEL_FEATURE].fillna("").astype(str).str.strip()
    for column in SUGGESTION_CONTEXT_FEATURES:
        result[column] = [
            context_by_model.get(model_name, {}).get(column)
            for model_name in model_names
        ]
    result["manufactured_month"] = np.nan
    result["operating_hours"] = np.nan
    result["posted_at"] = dt.datetime.now()
    return result


def prepare_feature_frame(frame: pd.DataFrame, *, reference_date: Optional[dt.date] = None) -> pd.DataFrame:
    def source_series(column: str, default: Any = np.nan) -> pd.Series:
        if column in frame:
            return frame[column]
        return pd.Series(default, index=frame.index)

    result = pd.DataFrame(index=frame.index)
    for column in CATEGORICAL_FEATURES:
        source = source_series(column)
        missing_value = "__UNKNOWN_MODEL__" if column == MODEL_FEATURE else "__UNKNOWN__"
        result[column] = source.fillna(missing_value).replace("", missing_value).astype(str)
    manufactured_year = pd.to_numeric(source_series("manufactured_year"), errors="coerce")
    manufactured_month = pd.to_numeric(source_series("manufactured_month"), errors="coerce")
    operating_hours = pd.to_numeric(source_series("operating_hours"), errors="coerce")
    posted_at = pd.to_datetime(source_series("posted_at", pd.NaT), errors="coerce")
    crawled_at = pd.to_datetime(source_series("crawled_at", pd.NaT), errors="coerce")
    fallback_year = (reference_date or dt.date.today()).year
    reference_at = posted_at.fillna(crawled_at)
    reference_year = reference_at.dt.year.fillna(fallback_year)
    result["manufactured_year"] = manufactured_year
    result["manufactured_month"] = manufactured_month
    result["manufactured_month_missing"] = manufactured_month.isna().astype(float)
    result["equipment_age"] = (reference_year - manufactured_year).clip(lower=0, upper=80)
    result["operating_hours_log"] = np.log1p(operating_hours.clip(lower=0))
    result["operating_hours_missing"] = operating_hours.isna().astype(float)
    result["reference_date_missing"] = reference_at.isna().astype(float)
    return result.loc[:, FEATURE_COLUMNS]


def build_preprocessor() -> ColumnTransformer:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore", dtype=np.float32),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("categorical", categorical, list(CATEGORICAL_FEATURES)),
            ("numeric", numeric, list(NUMERIC_FEATURES)),
        ],
        sparse_threshold=1.0,
    )


def leakage_group_series(frame: pd.DataFrame) -> pd.Series:
    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    row_nodes: dict[Any, str] = {}
    for index, row in frame.iterrows():
        source_id = str(row.get("source_listing_id", index))
        entity = str(row.get("entity_group_hash") or f"source:{source_id}")
        entity_node = f"entity:{entity}"
        find(entity_node)
        owner = str(row.get("owner_group_hash") or "").strip()
        if owner:
            union(entity_node, f"owner:{owner}")
        row_nodes[index] = entity_node
    return pd.Series({index: find(node) for index, node in row_nodes.items()})


def _temporal_group_order(frame: pd.DataFrame) -> list[str]:
    working = frame.copy()
    empty_dates = pd.Series(pd.NaT, index=working.index)
    posted = pd.to_datetime(
        working["posted_at"] if "posted_at" in working else empty_dates,
        errors="coerce",
    )
    crawled = pd.to_datetime(
        working["crawled_at"] if "crawled_at" in working else empty_dates,
        errors="coerce",
    )
    source_ids = working["id"] if "id" in working else pd.Series(range(len(working)), index=working.index)
    fallback = pd.Timestamp("1970-01-01") + pd.to_timedelta(
        pd.to_numeric(source_ids, errors="coerce").fillna(0), unit="s"
    )
    working["_sort_at"] = posted.fillna(crawled).fillna(fallback)
    working["_group"] = leakage_group_series(working)
    group_times = working.groupby("_group", sort=False)["_sort_at"].max().sort_values(kind="mergesort")
    return list(group_times.index)


def temporal_group_split(
    frame: pd.DataFrame,
    *,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if len(frame) < 3:
        raise ValueError("at least 3 cleaned rows are required")
    working = frame.copy()
    working["_group"] = leakage_group_series(working)
    groups = _temporal_group_order(working)
    if len(groups) < 3:
        raise ValueError("at least 3 independent entity groups are required")

    # Connected components vary greatly in size (a dealer may own many rows).
    # Pick chronological component boundaries by cumulative row count rather
    # than group count, while still keeping every component in exactly one split.
    group_sizes = working.groupby("_group", sort=False).size().reindex(groups)
    cumulative_rows = group_sizes.cumsum()
    total_rows = len(working)
    train_end = min(
        range(1, len(groups) - 1),
        key=lambda index: abs(
            int(cumulative_rows.iloc[index - 1]) - total_rows * train_ratio
        ),
    )
    validation_end = min(
        range(train_end + 1, len(groups)),
        key=lambda index: abs(
            int(cumulative_rows.iloc[index - 1])
            - total_rows * (train_ratio + validation_ratio)
        ),
    )
    train_groups = set(groups[:train_end])
    validation_groups = set(groups[train_end:validation_end])
    test_groups = set(groups[validation_end:])

    return (
        working[working["_group"].isin(train_groups)].drop(columns="_group"),
        working[working["_group"].isin(validation_groups)].drop(columns="_group"),
        working[working["_group"].isin(test_groups)].drop(columns="_group"),
    )


def regression_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Optional[float]]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    absolute_error = np.abs(actual - predicted)
    r2 = float(r2_score(actual, predicted)) if len(actual) >= 2 else None
    if r2 is not None and not math.isfinite(r2):
        r2 = None
    return {
        "mae_krw": float(mean_absolute_error(actual, predicted)),
        "rmse_krw": float(math.sqrt(mean_squared_error(actual, predicted))),
        "r2": r2,
        "wmape": float(absolute_error.sum() / max(np.abs(actual).sum(), 1.0)),
    }


def select_model_norm_training_rows(
    frame: pd.DataFrame,
    settings: PredictionSettings,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Keep only rows whose canonical model came directly from source model_norm."""
    working = frame.copy()
    input_rows = len(working)
    if MODEL_FEATURE not in working:
        working[MODEL_FEATURE] = None
    def numeric_source(column: str) -> pd.Series:
        source = working[column] if column in working else pd.Series(np.nan, index=working.index)
        return pd.to_numeric(source, errors="coerce")

    normalized_models = working[MODEL_FEATURE].map(normalize_model_name)
    price = numeric_source("price_krw")
    year = numeric_source("manufactured_year")
    max_year = dt.date.today().year + 1

    model_valid = normalized_models.ne("")
    price_valid = price.between(
        settings.price_min_krw,
        settings.price_max_krw,
        inclusive="both",
    )
    year_valid = year.between(1970, max_year, inclusive="both") & year.mod(1).eq(0)
    eligible = model_valid & price_valid & year_valid
    working = working.loc[eligible].copy()
    working[MODEL_FEATURE] = normalized_models.loc[eligible]
    working["price_krw"] = price.loc[eligible]
    working["manufactured_year"] = year.loc[eligible].astype(int)

    month = numeric_source("manufactured_month")
    month_valid = month.between(1, 12, inclusive="both") & month.mod(1).eq(0)
    working["manufactured_month"] = month.where(month_valid)
    hours = numeric_source("operating_hours")
    working["operating_hours"] = hours.where(hours.between(0, 200_000, inclusive="both"))

    return working, {
        "input_cleaned_rows": int(input_rows),
        "excluded_missing_model_norm": int((~model_valid).sum()),
        "excluded_invalid_price": int((model_valid & ~price_valid).sum()),
        "excluded_invalid_year": int((model_valid & price_valid & ~year_valid).sum()),
        "eligible_model_norm_rows": int(len(working)),
        "eligible_model_norm_count": int(working[MODEL_FEATURE].nunique()),
        "missing_manufactured_month": int(working["manufactured_month"].isna().sum()),
        "missing_operating_hours": int(working["operating_hours"].isna().sum()),
    }


def filter_training_price_outliers(
    train_frame: pd.DataFrame,
    *,
    maximum_fraction: float = 0.03,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove only extreme model/year residuals from train; never filter validation/test."""
    candidates: list[dict[str, Any]] = []
    for model_norm, group in train_frame.groupby(MODEL_FEATURE, sort=True):
        years = pd.to_numeric(group["manufactured_year"], errors="coerce")
        prices = pd.to_numeric(group["price_krw"], errors="coerce")
        valid = years.notna() & prices.gt(0)
        if valid.sum() < 12 or years.loc[valid].nunique() < 3:
            continue
        if float(years.loc[valid].max() - years.loc[valid].min()) < 3:
            continue
        indexes = group.index[valid]
        centered_years = years.loc[indexes] - float(years.loc[indexes].median())
        log_prices = np.log1p(prices.loc[indexes].to_numpy(dtype=float))
        try:
            estimator = HuberRegressor(
                epsilon=1.35,
                alpha=0.1,
                max_iter=500,
            ).fit(centered_years.to_numpy(dtype=float).reshape(-1, 1), log_prices)
        except (FloatingPointError, ValueError):
            continue
        residual = log_prices - estimator.predict(
            centered_years.to_numpy(dtype=float).reshape(-1, 1)
        )
        center = float(np.median(residual))
        mad = float(np.median(np.abs(residual - center)))
        threshold = max(4.5 * 1.4826 * mad, math.log(2.5))
        for index, value in zip(indexes, residual):
            deviation = abs(float(value) - center)
            if deviation <= threshold:
                continue
            row = train_frame.loc[index]
            candidates.append(
                {
                    "index": index,
                    "source_listing_id": row.get("source_listing_id"),
                    "model_norm": model_norm,
                    "manufactured_year": int(row["manufactured_year"]),
                    "price_krw": int(row["price_krw"]),
                    "absolute_log_residual": deviation,
                    "threshold": threshold,
                    "reason": "model_year_huber_residual",
                }
            )

    maximum_rows = max(0, int(math.floor(len(train_frame) * maximum_fraction)))
    selected = sorted(
        candidates,
        key=lambda row: (-row["absolute_log_residual"], str(row["index"])),
    )[:maximum_rows]
    selected_indexes = {row["index"] for row in selected}
    audit_columns = (
        "source_listing_id",
        "model_norm",
        "manufactured_year",
        "price_krw",
        "absolute_log_residual",
        "threshold",
        "reason",
    )
    audit = pd.DataFrame(selected).reindex(columns=audit_columns)
    return train_frame.drop(index=list(selected_indexes)), audit


def _model_builders(
    random_seed: int,
    requested: Iterable[str],
) -> tuple[dict[str, Any], dict[str, str]]:
    builders: dict[str, Any] = {}
    errors: dict[str, str] = {}
    requested_set = set(requested)
    if "xgboost" in requested_set:
        try:
            from xgboost import XGBRegressor

            builders["xgboost"] = lambda: XGBRegressor(
                objective="reg:squarederror",
                tree_method="hist",
                n_estimators=2_000,
                learning_rate=0.03,
                max_depth=8,
                min_child_weight=3,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_alpha=0.05,
                reg_lambda=1.0,
                eval_metric="mae",
                early_stopping_rounds=100,
                random_state=random_seed,
                n_jobs=-1,
            )
        except (ImportError, OSError) as error:
            errors["xgboost"] = f"{type(error).__name__}: {error}"
    if "lightgbm" in requested_set:
        try:
            import lightgbm as lgb

            builders["lightgbm"] = lambda: lgb.LGBMRegressor(
                objective="regression_l1",
                n_estimators=2_000,
                learning_rate=0.03,
                num_leaves=63,
                max_depth=-1,
                min_child_samples=20,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_alpha=0.05,
                reg_lambda=1.0,
                random_state=random_seed,
                n_jobs=-1,
                verbosity=-1,
            )
        except (ImportError, OSError) as error:
            errors["lightgbm"] = f"{type(error).__name__}: {error}"
    return builders, errors


def _fit_estimator(name: str, estimator, x_train, y_train, x_validation, y_validation) -> None:
    if name == "xgboost":
        estimator.fit(
            x_train,
            y_train,
            eval_set=[(x_validation, y_validation)],
            verbose=False,
        )
        return
    if name == "lightgbm":
        import lightgbm as lgb

        estimator.fit(
            x_train,
            y_train,
            eval_set=[(x_validation, y_validation)],
            eval_metric="mae",
            callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(0)],
        )
        return
    raise ValueError(f"unsupported model: {name}")


def _save_estimator(name: str, estimator, output_dir: Path) -> str:
    if name == "xgboost":
        path = output_dir / "xgboost.ubj"
        estimator.save_model(path)
        return path.name
    if name == "lightgbm":
        path = output_dir / "lightgbm.txt"
        best_iteration = getattr(estimator, "best_iteration_", None)
        estimator.booster_.save_model(str(path), num_iteration=best_iteration)
        return path.name
    raise ValueError(f"unsupported model: {name}")


def train_from_frame(
    frame: pd.DataFrame,
    settings: PredictionSettings,
    *,
    algorithms: Iterable[str] = ("xgboost", "lightgbm"),
    minimum_rows: Optional[int] = None,
    promote: bool = True,
) -> dict[str, Any]:
    requested = list(dict.fromkeys(str(name).lower() for name in algorithms))
    allowed = {"xgboost", "lightgbm"}
    unknown = set(requested) - allowed
    if unknown:
        raise ValueError(f"unsupported algorithms: {sorted(unknown)}")
    if not requested:
        raise ValueError("at least one algorithm is required")
    working, data_quality = select_model_norm_training_rows(frame, settings)
    required_rows = int(minimum_rows or settings.minimum_training_rows)
    if len(working) < required_rows:
        raise ValueError(
            f"not enough model_norm training rows: {len(working)} < {required_rows}"
        )

    builders, builder_errors = _model_builders(settings.random_seed, requested)
    missing = [name for name in requested if name not in builders]
    if missing:
        details = "; ".join(builder_errors.get(name, "not installed") for name in missing)
        raise RuntimeError(
            f"unavailable model dependency for {missing}: {details}; "
            "install prediction/requirements.txt"
        )

    train_before_outliers, validation_frame, test_frame = temporal_group_split(working)
    train_frame, outlier_audit = filter_training_price_outliers(train_before_outliers)
    data_quality["train_rows_before_outlier_filter"] = int(len(train_before_outliers))
    data_quality["train_price_outliers_removed"] = int(len(outlier_audit))
    data_quality["train_rows_after_outlier_filter"] = int(len(train_frame))
    if len(train_frame) < required_rows:
        raise ValueError(
            f"not enough training rows after outlier filtering: {len(train_frame)} < {required_rows}"
        )
    # Suggestions are part of the online input contract. Build them from the
    # training split only so validation/test rows cannot leak representative
    # category/manufacturer context into either the API or serving metrics.
    suggestion_payload = build_model_suggestions(train_frame)
    web_serving_validation_frame = prepare_web_serving_frame(
        validation_frame, suggestion_payload
    )
    web_serving_test_frame = prepare_web_serving_frame(test_frame, suggestion_payload)
    suggested_models = {
        str(item.get("model_name") or "").strip()
        for item in suggestion_payload.get("models", [])
        if isinstance(item, dict) and str(item.get("model_name") or "").strip()
    }
    api_serving_validation_mask = (
        validation_frame[MODEL_FEATURE]
        .fillna("")
        .astype(str)
        .str.strip()
        .isin(suggested_models)
    )
    api_serving_test_mask = (
        test_frame[MODEL_FEATURE].fillna("").astype(str).str.strip().isin(suggested_models)
    )
    api_serving_validation_frame = web_serving_validation_frame.loc[
        api_serving_validation_mask
    ].copy()
    api_serving_test_frame = web_serving_test_frame.loc[api_serving_test_mask].copy()
    if api_serving_validation_frame.empty or api_serving_test_frame.empty:
        raise ValueError("validation/test split has no model_norm values available to the API")
    preprocessor = build_preprocessor()
    x_train = preprocessor.fit_transform(prepare_feature_frame(train_frame))
    x_validation = preprocessor.transform(prepare_feature_frame(validation_frame))
    x_test = preprocessor.transform(prepare_feature_frame(test_frame))
    x_web_serving_validation = preprocessor.transform(
        prepare_feature_frame(web_serving_validation_frame)
    )
    x_web_serving_test = preprocessor.transform(
        prepare_feature_frame(web_serving_test_frame)
    )
    x_api_serving_validation = preprocessor.transform(
        prepare_feature_frame(api_serving_validation_frame)
    )
    x_api_serving_test = preprocessor.transform(
        prepare_feature_frame(api_serving_test_frame)
    )
    y_train_raw = train_frame["price_krw"].to_numpy(dtype=float)
    y_validation_raw = validation_frame["price_krw"].to_numpy(dtype=float)
    y_test_raw = test_frame["price_krw"].to_numpy(dtype=float)
    y_api_serving_validation_raw = api_serving_validation_frame["price_krw"].to_numpy(
        dtype=float
    )
    y_api_serving_test_raw = api_serving_test_frame["price_krw"].to_numpy(dtype=float)
    y_train = np.log1p(y_train_raw)
    y_validation = np.log1p(y_validation_raw)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_dir = settings.artifact_dir / "price" / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    preprocessor_path = output_dir / "preprocessor.joblib"
    joblib.dump(preprocessor, preprocessor_path)
    preprocessor_path.chmod(0o600)

    suggestions_path = output_dir / "model_suggestions.json"
    write_json_atomic(suggestions_path, suggestion_payload)
    outliers_path = output_dir / "training_outliers.csv"
    outlier_audit.to_csv(outliers_path, index=False, encoding="utf-8")
    outliers_path.chmod(0o600)

    member_frames = []
    for split_name, split_frame in (
        ("train", train_frame),
        ("validation", validation_frame),
        ("test", test_frame),
    ):
        members = split_frame.reindex(
            columns=[
                "source_listing_id",
                "entity_group_hash",
                "owner_group_hash",
                "posted_at",
                "price_krw",
            ]
        ).copy()
        members.insert(0, "split", split_name)
        members["feature_hash"] = [
            hashlib.sha256(
                json.dumps(
                    {
                        key: None if pd.isna(value) else value
                        for key, value in row.items()
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()
            for row in prepare_feature_frame(split_frame).to_dict(orient="records")
        ]
        member_frames.append(members)
    members_path = output_dir / "dataset_members.csv"
    pd.concat(member_frames, ignore_index=True).to_csv(
        members_path,
        index=False,
        encoding="utf-8",
    )
    members_path.chmod(0o600)
    model_metrics: dict[str, Any] = {}
    model_files: dict[str, str] = {}
    for name in requested:
        estimator = builders[name]()
        _fit_estimator(name, estimator, x_train, y_train, x_validation, y_validation)
        validation_prediction = np.maximum(0.0, np.expm1(estimator.predict(x_validation)))
        test_prediction = np.maximum(0.0, np.expm1(estimator.predict(x_test)))
        web_serving_validation_prediction = np.maximum(
            0.0,
            np.expm1(estimator.predict(x_web_serving_validation)),
        )
        web_serving_test_prediction = np.maximum(
            0.0,
            np.expm1(estimator.predict(x_web_serving_test)),
        )
        api_serving_test_prediction = np.maximum(
            0.0,
            np.expm1(estimator.predict(x_api_serving_test)),
        )
        api_serving_validation_prediction = np.maximum(
            0.0,
            np.expm1(estimator.predict(x_api_serving_validation)),
        )
        model_metrics[name] = {
            "validation": regression_metrics(y_validation_raw, validation_prediction),
            "test": regression_metrics(y_test_raw, test_prediction),
            "web_serving_validation": regression_metrics(
                y_validation_raw,
                web_serving_validation_prediction,
            ),
            "web_serving_test": regression_metrics(
                y_test_raw,
                web_serving_test_prediction,
            ),
            "api_serving_test": regression_metrics(
                y_api_serving_test_raw,
                api_serving_test_prediction,
            ),
            "api_serving_validation": regression_metrics(
                y_api_serving_validation_raw,
                api_serving_validation_prediction,
            ),
            "best_iteration": int(
                getattr(estimator, "best_iteration", getattr(estimator, "best_iteration_", 0)) or 0
            ),
        }
        model_files[name] = _save_estimator(name, estimator, output_dir)
        (output_dir / model_files[name]).chmod(0o600)

    best_model = min(
        requested,
        key=lambda name: model_metrics[name]["api_serving_validation"]["mae_krw"],
    )
    baseline_prediction = np.full_like(y_test_raw, np.median(y_train_raw), dtype=float)
    artifact_checksums = {
        "preprocessor.joblib": sha256_file(preprocessor_path),
        "dataset_members.csv": sha256_file(members_path),
        "model_suggestions.json": sha256_file(suggestions_path),
        "training_outliers.csv": sha256_file(outliers_path),
        **{
            filename: sha256_file(output_dir / filename)
            for filename in model_files.values()
        },
    }
    resolver_path = settings.artifact_dir / "cleaning" / "model_name_resolver.joblib"
    config_fingerprint_payload = {
        "min_model_frequency": settings.min_model_frequency,
        "model_confidence_threshold": settings.model_confidence_threshold,
        "minimum_training_rows": required_rows,
        "price_min_krw": settings.price_min_krw,
        "price_max_krw": settings.price_max_krw,
        "random_seed": settings.random_seed,
        "features": list(FEATURE_COLUMNS),
        "model_policy": "source_model_norm_present_only",
        "split_policy": "connected_components_cumulative_row_boundary_v1",
        "selection_metric": "api_serving_validation.mae_krw",
        "training_outlier_policy": "per_model_huber_year_log_price_residual_v1",
    }
    config_fingerprint = hashlib.sha256(
        json.dumps(config_fingerprint_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    manifest = {
        "format_version": 1,
        "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "best_model": best_model,
        "selection_metric": "api_serving_validation.mae_krw",
        "models": model_files,
        "metrics": model_metrics,
        "baseline_test": regression_metrics(y_test_raw, baseline_prediction),
        "rows": {
            "total": len(train_frame) + len(validation_frame) + len(test_frame),
            "eligible_before_outlier_filter": len(working),
            "train": len(train_frame),
            "validation": len(validation_frame),
            "test": len(test_frame),
            "api_serving_validation": len(api_serving_validation_frame),
            "api_serving_test": len(api_serving_test_frame),
        },
        "data_quality": {
            **data_quality,
            "model_policy": "source_model_norm_present_only",
            "target_missing_policy": "exclude",
            "manufactured_year_missing_policy": "exclude",
            "optional_numeric_policy": "median_impute_with_missing_indicator",
            "categorical_missing_policy": "explicit_unknown_category",
            "outlier_policy": {
                "scope": "training_split_only",
                "method": "per_model_huber_year_log_price_residual",
                "minimum_model_rows": 12,
                "minimum_unique_years": 3,
                "minimum_year_span": 3,
                "minimum_log_threshold": math.log(2.5),
                "robust_sigma_multiplier": 4.5,
                "maximum_removed_fraction": 0.03,
            },
        },
        "features": list(FEATURE_COLUMNS),
        "feature_encoding": {
            "categorical": "one_hot",
            "categorical_features": list(CATEGORICAL_FEATURES),
            "categorical_cardinality": {
                column: int(len(categories))
                for column, categories in zip(
                    CATEGORICAL_FEATURES,
                    preprocessor.named_transformers_["categorical"].named_steps["onehot"].categories_,
                )
            },
            "model_norm": "exact_one_hot",
            "web_serving": {
                "inputs": ["model_norm", "manufactured_year"],
                "categorical_context": "dominant_observed_tuple_per_model",
                "manufactured_month": "missing",
                "operating_hours": "missing",
            },
        },
        "target": "log1p(price_krw)",
        "split": {
            "method": "entity-owner connected-component chronological cumulative-row boundary",
            "target_row_ratios": {
                "train": 0.70,
                "validation": 0.15,
                "test": 0.15,
            },
            "rows_before_train_outlier_filter": {
                "train": len(train_before_outliers),
                "validation": len(validation_frame),
                "test": len(test_frame),
            },
        },
        "dataset_members": members_path.name,
        "training_outliers": outliers_path.name,
        "model_suggestions": suggestions_path.name,
        "dataset_sha256": artifact_checksums[members_path.name],
        "config_sha256": config_fingerprint,
        "model_name_resolver_sha256": sha256_file(resolver_path) if resolver_path.exists() else None,
        "preprocessor": "preprocessor.joblib",
        "artifact_sha256": artifact_checksums,
        "code": code_revision(),
        "versions": {
            name: package_version(name)
            for name in (
                "python",
                "numpy",
                "pandas",
                "scipy",
                "scikit-learn",
                "xgboost",
                "lightgbm",
                "joblib",
            )
        },
    }
    manifest_path = output_dir / "manifest.json"
    write_json_atomic(manifest_path, manifest)
    if promote:
        promote_artifact(settings, output_dir)
    return {**manifest, "artifact_dir": str(output_dir)}


def train_price_models(
    settings: PredictionSettings,
    *,
    algorithms: Iterable[str] = ("xgboost", "lightgbm"),
    minimum_rows: Optional[int] = None,
) -> dict[str, Any]:
    with WarehouseRepository(settings) as repository:
        frame = repository.cleaned_frame()
        result = train_from_frame(
            frame,
            settings,
            algorithms=algorithms,
            minimum_rows=minimum_rows,
            promote=False,
        )
        run_id = repository.record_training_run(
            artifact_path=Path(result["artifact_dir"]),
            best_model=result["best_model"],
            train_rows=int(result["rows"]["train"]),
            validation_rows=int(result["rows"]["validation"]),
            metrics={
                "models": result["metrics"],
                "baseline_test": result["baseline_test"],
                "dataset_sha256": result["dataset_sha256"],
                "config_sha256": result["config_sha256"],
                "model_name_resolver_sha256": result["model_name_resolver_sha256"],
                "artifact_sha256": result["artifact_sha256"],
                "code": result["code"],
            },
        )
        result["training_run_id"] = run_id
        promote_artifact(settings, Path(result["artifact_dir"]))
        return result
