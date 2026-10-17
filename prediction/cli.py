from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from prediction import __version__
from prediction.cleaning import run_cleaning
from prediction.config import DEFAULT_CONFIG_PATH, PredictionSettings, load_settings
from prediction.extract import export_listings_csv
from prediction.notebook_workflow import clean_records_in_memory, records_from_frame
from prediction.predictor import PricePredictor, predict_csv
from prediction.schema import initialize_warehouse
from prediction.training import train_from_frame, train_price_models
from prediction.warehouse import ingest_csv


def _json_default(value: Any) -> Any:
    if isinstance(value, (Path, dt.date, dt.datetime)):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def print_result(result: Any) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m prediction",
        description="운영 listings 스냅샷 정제 및 중장비 가격 예측 파이프라인",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"prediction 설정 JSON 경로(기본: {DEFAULT_CONFIG_PATH.name} 또는 .env)",
    )
    parser.add_argument("--debug", action="store_true", help="오류 traceback 출력")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="별도 prediction warehouse 테이블 생성")

    export = commands.add_parser("export", help="운영 listings를 읽기 전용 CSV로 추출")
    export.add_argument("--output", type=Path, help="출력 CSV 경로")
    export.add_argument("--after-id", type=int, default=0, help="이 id보다 큰 행만 추출")
    export.add_argument("--limit", type=int, help="개발용 최대 행 수")
    export.add_argument("--batch-size", type=int, default=1000)

    ingest = commands.add_parser("ingest", help="CSV snapshot을 products_raw에 적재")
    ingest.add_argument("--csv", type=Path, required=True)
    ingest.add_argument("--batch-size", type=int, default=500)

    clean = commands.add_parser("clean", help="seed 모델 사전 생성 후 clean/dirty 데이터 정제")
    clean.add_argument(
        "--recheck-needs-review",
        action="store_true",
        help="이전 low-confidence 행도 확장된 사전으로 다시 추정",
    )

    train = commands.add_parser("train", help="XGBoost/LightGBM 가격 모델 학습")
    train.add_argument(
        "--algorithm",
        action="append",
        choices=("xgboost", "lightgbm"),
        help="학습 모델(여러 번 지정 가능, 기본 둘 다)",
    )
    train.add_argument("--minimum-rows", type=int)

    train_snapshot = commands.add_parser(
        "train-snapshot",
        help="CSV snapshot을 메모리에서 정제해 가격 모델 학습",
    )
    train_snapshot.add_argument("--csv", type=Path, required=True)
    train_snapshot.add_argument(
        "--algorithm",
        action="append",
        choices=("xgboost", "lightgbm"),
        help="기본 둘 다",
    )
    train_snapshot.add_argument("--minimum-rows", type=int)
    train_snapshot.add_argument(
        "--promote",
        action="store_true",
        help="검증 완료 artifact를 latest.json으로 승격",
    )

    predict = commands.add_parser("predict", help="최신 또는 지정 artifact로 가격 예측")
    predict.add_argument("--artifact-dir", type=Path)
    predict.add_argument("--algorithm", choices=("xgboost", "lightgbm"))
    predict.add_argument("--input-csv", type=Path)
    predict.add_argument("--output-csv", type=Path)
    predict.add_argument("--model-name")
    predict.add_argument("--year", type=int)
    predict.add_argument("--month", type=int)
    predict.add_argument("--operating-hours", type=float)
    predict.add_argument("--manufacturer")
    predict.add_argument("--category-code")
    predict.add_argument("--category-name")
    predict.add_argument("--equipment-status")
    predict.add_argument("--source-site", default="manual")
    predict.add_argument("--location")

    run_all = commands.add_parser("run-all", help="전체 snapshot → ingest → clean → train 실행")
    run_all.add_argument("--limit", type=int, help="개발용 최대 source 행 수")
    run_all.add_argument("--skip-train", action="store_true")
    run_all.add_argument(
        "--algorithm",
        action="append",
        choices=("xgboost", "lightgbm"),
        help="기본 둘 다",
    )
    run_all.add_argument("--minimum-rows", type=int)
    run_all.add_argument("--recheck-needs-review", action="store_true")
    return parser


def _settings(args: argparse.Namespace) -> PredictionSettings:
    return load_settings(args.config)


def _predict(args: argparse.Namespace, settings: PredictionSettings) -> dict[str, Any]:
    predictor = PricePredictor(
        settings,
        artifact_dir=args.artifact_dir,
        algorithm=args.algorithm,
    )
    if args.input_csv:
        if not args.output_csv:
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            args.output_csv = settings.data_dir / "predictions" / f"predictions_{stamp}.csv"
        return predict_csv(predictor, args.input_csv, args.output_csv)
    if not args.model_name or not args.year:
        raise ValueError("single prediction requires --model-name and --year")
    return predictor.predict_one(
        model_norm=args.model_name,
        manufactured_year=args.year,
        manufactured_month=args.month,
        operating_hours=args.operating_hours,
        manufacturer=args.manufacturer,
        category_code=args.category_code,
        category_name=args.category_name,
        equipment_status=args.equipment_status,
        source_site=args.source_site,
        location=args.location,
        posted_at=dt.datetime.now(),
    )


def dispatch(args: argparse.Namespace) -> Any:
    settings = _settings(args)
    if args.command == "init":
        initialize_warehouse(settings)
        return {"status": "initialized", "database": settings.warehouse_mysql.database}
    if args.command == "export":
        return export_listings_csv(
            settings,
            output_path=args.output,
            after_id=args.after_id,
            limit=args.limit,
            batch_size=args.batch_size,
        )
    if args.command == "ingest":
        return ingest_csv(settings, args.csv, batch_size=args.batch_size)
    if args.command == "clean":
        return run_cleaning(settings, recheck_needs_review=args.recheck_needs_review)
    if args.command == "train":
        return train_price_models(
            settings,
            algorithms=args.algorithm or ("xgboost", "lightgbm"),
            minimum_rows=args.minimum_rows,
        )
    if args.command == "train-snapshot":
        snapshot = pd.read_csv(args.csv, low_memory=False)
        cleaning = clean_records_in_memory(records_from_frame(snapshot), settings)
        training = train_from_frame(
            cleaning.cleaned_frame,
            settings,
            algorithms=args.algorithm or ("xgboost", "lightgbm"),
            minimum_rows=args.minimum_rows,
            promote=args.promote,
        )
        return {
            "csv_path": str(args.csv.expanduser().resolve()),
            "raw_rows": len(cleaning.raw_frame),
            "cleaned_rows": len(cleaning.cleaned_frame),
            "cleaning_status": {
                str(status): int(count)
                for status, count in cleaning.audit_frame["status"].value_counts().items()
            },
            "seed_models": len(cleaning.catalog_frame),
            "training": training,
            "promoted": bool(args.promote),
        }
    if args.command == "predict":
        return _predict(args, settings)
    if args.command == "run-all":
        # Full snapshots are deliberate: an id-only watermark misses updates to
        # existing listings. At ~20k rows this is safer and still inexpensive.
        initialize_warehouse(settings)
        exported = export_listings_csv(settings, after_id=0, limit=args.limit)
        ingested = ingest_csv(settings, Path(exported["csv_path"]))
        cleaned = run_cleaning(
            settings,
            recheck_needs_review=args.recheck_needs_review,
        )
        result: dict[str, Any] = {
            "export": exported,
            "ingest": ingested,
            "clean": cleaned,
        }
        if not args.skip_train:
            result["train"] = train_price_models(
                settings,
                algorithms=args.algorithm or ("xgboost", "lightgbm"),
                minimum_rows=args.minimum_rows,
            )
        return result
    raise ValueError(f"unknown command: {args.command}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        print_result(dispatch(args))
        return 0
    except Exception as error:  # noqa: BLE001 - CLI converts failures to a non-zero exit.
        print(f"[prediction] {type(error).__name__}: {error}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1
