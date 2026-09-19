from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.common import (
    DEFAULT_CONFIG_PATH,
    MODEL_OBSERVED_CSV_PATH,
    clean_text,
    load_mysql_config,
    mysql_connect,
    normalize_model_key,
)


ALLOWED_MODEL = re.compile(r"^[0-9A-Za-z가-힣][0-9A-Za-z가-힣 ._+()/\-]{0,39}$")
GENERIC_WORDS = {
    "굴삭기", "굴착기", "중장비", "EXCAVATOR", "LOADER", "CRANE", "DOZER",
    "FORKLIFT", "UNKNOWN", "OTHER", "NONE", "미상", "기타", "협의", "문의",
}


def validated_model(value: object, manufacturer: object = None) -> str | None:
    model = clean_text(value)
    if not model or not ALLOWED_MODEL.fullmatch(model) or not any(char.isdigit() for char in model):
        return None
    if model.upper() in GENERIC_WORDS:
        return None
    if model.isdigit() and len(model) == 4 and 1900 <= int(model) <= 2100:
        return None
    # Numeric model names exist (for example CAT 320), but longer bare numbers
    # without a manufacturer are more likely serials, years, or meter values.
    if model.isdigit() and len(model) > 3 and not clean_text(manufacturer):
        return None
    return model


def collect_observed_models(config_path: Path) -> list[dict[str, str]]:
    config = load_mysql_config(config_path)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT model_name, manufacturer, source_site, COUNT(*) AS listing_count
                FROM listings
                WHERE model_name IS NOT NULL AND TRIM(model_name) <> ''
                GROUP BY model_name, manufacturer, source_site
                ORDER BY listing_count DESC, model_name ASC
                """
            )
            rows = cursor.fetchall()

    by_key: dict[str, dict[str, str]] = {}
    for row in rows:
        model = validated_model(row.get("model_name"), row.get("manufacturer"))
        if not model:
            continue
        key = normalize_model_key(model)
        if not key or key in by_key:
            continue
        by_key[key] = {
            "canonical_model": model,
            "manufacturer": clean_text(row.get("manufacturer")),
            "source_url": f"observed:{clean_text(row.get('source_site')) or 'unknown'}",
        }
    return sorted(by_key.values(), key=lambda row: normalize_model_key(row["canonical_model"]))


def write_catalog(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("canonical_model", "manufacturer", "source_url"))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DB에서 신뢰 가능한 관측 모델명을 정규화 카탈로그로 생성")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=MODEL_OBSERVED_CSV_PATH)
    args = parser.parse_args(argv)
    rows = collect_observed_models(args.config)
    write_catalog(rows, args.output)
    print(f"[model-catalog] observed_models={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
