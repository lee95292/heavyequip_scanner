from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

from prediction.config import PredictionSettings
from prediction.db import mysql_connect, quote_identifier


SOURCE_COLUMNS = (
    "id",
    "content_hash",
    "origin",
    "source_site",
    "crawl_url",
    "detail_url",
    "pid",
    "category_code",
    "category_name",
    "listing_name",
    "model_name",
    "model_norm",
    "description",
    "price",
    "price_krw",
    "contact",
    "posted_date",
    "posted_at",
    "crawled_at",
    "manufacturer",
    "manufactured_ym",
    "location",
    "seller",
    "status",
    "view_count",
    "raw_json",
    "payload_json",
    "created_at",
    "updated_at",
)

CSV_COLUMNS = ("source_listing_id",) + SOURCE_COLUMNS[1:]


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def default_export_path(settings: PredictionSettings) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return settings.data_dir / "raw" / f"listings_{stamp}.csv"


def export_listings_csv(
    settings: PredictionSettings,
    *,
    output_path: Optional[Path] = None,
    after_id: int = 0,
    limit: Optional[int] = None,
    batch_size: int = 1000,
) -> dict[str, Any]:
    output = Path(output_path or default_export_path(settings)).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(f"{output}.part")
    source_table = quote_identifier(settings.source_table)
    selected_columns = ", ".join(quote_identifier(column) for column in SOURCE_COLUMNS)
    sql = (
        f"SELECT {selected_columns} FROM {source_table} "
        "WHERE id > %s ORDER BY id ASC"
    )
    params: list[Any] = [max(0, int(after_id))]
    if limit is not None:
        sql += " LIMIT %s"
        params.append(max(0, int(limit)))

    count = 0
    max_source_id = max(0, int(after_id))
    try:
        with mysql_connect(settings.source_mysql, streaming=True) as connection:
            with connection.cursor() as cursor, temporary.open(
                "w", encoding="utf-8-sig", newline=""
            ) as csv_file:
                cursor.execute(sql, params)
                writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                while True:
                    rows = cursor.fetchmany(max(1, int(batch_size)))
                    if not rows:
                        break
                    for row in rows:
                        source_id = int(row.get("id") or 0)
                        exported = {
                            "source_listing_id": source_id,
                            **{column: _csv_value(row.get(column)) for column in SOURCE_COLUMNS[1:]},
                        }
                        writer.writerow(exported)
                        count += 1
                        max_source_id = max(max_source_id, source_id)
        temporary.replace(output)
        output.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    metadata = {
        "source_table": settings.source_table,
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "after_id": max(0, int(after_id)),
        "row_count": count,
        "max_source_listing_id": max_source_id,
        "csv_path": str(output),
    }
    metadata_path = output.with_suffix(f"{output.suffix}.meta.json")
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metadata_path.chmod(0o600)
    return metadata
