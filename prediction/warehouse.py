from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
import pymysql

from prediction.config import PredictionSettings
from prediction.db import mysql_connect, quote_identifier
from prediction.extract import CSV_COLUMNS
from prediction.schema import (
    CLEANED_TABLE,
    CLEANING_RUNS_TABLE,
    MODEL_CATALOG_TABLE,
    RAW_TABLE,
    TRAINING_RUNS_TABLE,
)


RAW_INSERT_COLUMNS = (
    "source_listing_id",
    "content_hash",
    "source_revision_hash",
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
    "source_created_at",
    "source_updated_at",
)

REVISION_COLUMNS = (
    "content_hash",
    "source_site",
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
    "manufacturer",
    "manufactured_ym",
    "location",
    "seller",
    "status",
)
CSV_FIELD_LIMIT = 128 * 1024 * 1024


def _validate_csv_header(fieldnames: Optional[list[str]]) -> None:
    missing = set(CSV_COLUMNS) - set(fieldnames or ())
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")


def _empty_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _integer(value: Any) -> Optional[int]:
    value = _empty_to_none(value)
    if value is None:
        return None
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _json_text(value: Any) -> Optional[str]:
    value = _empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = str(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {"unparsed": text}
    return json.dumps(parsed, ensure_ascii=False, sort_keys=True)


def _raw_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "source_listing_id": int(row["source_listing_id"]),
        "content_hash": _empty_to_none(row.get("content_hash")),
        "origin": _empty_to_none(row.get("origin")),
        "source_site": _empty_to_none(row.get("source_site")),
        "crawl_url": _empty_to_none(row.get("crawl_url")),
        "detail_url": _empty_to_none(row.get("detail_url")),
        "pid": _empty_to_none(row.get("pid")),
        "category_code": _empty_to_none(row.get("category_code")),
        "category_name": _empty_to_none(row.get("category_name")),
        "listing_name": _empty_to_none(row.get("listing_name")),
        "model_name": _empty_to_none(row.get("model_name")),
        "model_norm": _empty_to_none(row.get("model_norm")),
        "description": _empty_to_none(row.get("description")),
        "price": _empty_to_none(row.get("price")),
        "price_krw": _integer(row.get("price_krw")),
        "contact": _empty_to_none(row.get("contact")),
        "posted_date": _empty_to_none(row.get("posted_date")),
        "posted_at": _empty_to_none(row.get("posted_at")),
        "crawled_at": _empty_to_none(row.get("crawled_at")),
        "manufacturer": _empty_to_none(row.get("manufacturer")),
        "manufactured_ym": _empty_to_none(row.get("manufactured_ym")),
        "location": _empty_to_none(row.get("location")),
        "seller": _empty_to_none(row.get("seller")),
        "status": _empty_to_none(row.get("status")),
        "view_count": _integer(row.get("view_count")),
        "raw_json": _json_text(row.get("raw_json")),
        "payload_json": _json_text(row.get("payload_json")),
        "source_created_at": _empty_to_none(row.get("created_at") or row.get("source_created_at")),
        "source_updated_at": _empty_to_none(row.get("updated_at") or row.get("source_updated_at")),
    }
    revision_payload = {column: payload.get(column) for column in REVISION_COLUMNS}
    try:
        raw_object = json.loads(payload["raw_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        raw_object = {}
    raw_detail = raw_object.get("detail") if isinstance(raw_object, dict) else None
    revision_payload["raw_detail"] = raw_detail if isinstance(raw_detail, dict) else {}
    payload["source_revision_hash"] = hashlib.sha256(
        json.dumps(
            revision_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return payload


def ingest_csv(
    settings: PredictionSettings,
    csv_path: Path,
    *,
    batch_size: int = 500,
) -> dict[str, Any]:
    path = Path(csv_path).expanduser().resolve()
    table = quote_identifier(RAW_TABLE)
    column_sql = ", ".join(quote_identifier(column) for column in RAW_INSERT_COLUMNS)
    values_sql = ", ".join(f"%({column})s" for column in RAW_INSERT_COLUMNS)
    mutable_columns = [column for column in RAW_INSERT_COLUMNS if column != "source_listing_id"]
    update_sql = ",\n                    ".join(
        f"{quote_identifier(column)}=VALUES({quote_identifier(column)})" for column in mutable_columns
    )
    sql = f"""
        INSERT INTO {table} ({column_sql})
        VALUES ({values_sql})
        ON DUPLICATE KEY UPDATE
            checked=IF(NOT (source_revision_hash <=> VALUES(source_revision_hash)), 0, checked),
            check_status=IF(
                NOT (source_revision_hash <=> VALUES(source_revision_hash)), 'pending', check_status
            ),
            check_message=IF(
                NOT (source_revision_hash <=> VALUES(source_revision_hash)), NULL, check_message
            ),
            checked_at=IF(
                NOT (source_revision_hash <=> VALUES(source_revision_hash)), NULL, checked_at
            ),
            {update_sql},
            updated_at=CURRENT_TIMESTAMP
    """
    read_count = 0
    affected_count = 0
    batch: list[dict[str, Any]] = []
    if csv.field_size_limit() < CSV_FIELD_LIMIT:
        csv.field_size_limit(CSV_FIELD_LIMIT)
    with path.open("r", encoding="utf-8-sig", newline="") as source_file, mysql_connect(
        settings.warehouse_mysql, autocommit=False
    ) as connection:
        reader = csv.DictReader(source_file)
        _validate_csv_header(reader.fieldnames)
        with connection.cursor() as cursor:
            try:
                for row in reader:
                    batch.append(_raw_payload(row))
                    read_count += 1
                    if len(batch) >= max(1, int(batch_size)):
                        affected_count += cursor.executemany(sql, batch)
                        connection.commit()
                        batch.clear()
                if batch:
                    affected_count += cursor.executemany(sql, batch)
                    connection.commit()
            except BaseException:
                connection.rollback()
                raise
    return {
        "csv_path": str(path),
        "read_rows": read_count,
        "affected_rows": int(affected_count),
    }


class WarehouseRepository:
    def __init__(self, settings: PredictionSettings, *, autocommit: bool = True):
        self.settings = settings
        self.connection = mysql_connect(settings.warehouse_mysql, autocommit=autocommit)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "WarehouseRepository":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False

    def max_source_listing_id(self) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COALESCE(MAX(source_listing_id), 0) AS max_id FROM {quote_identifier(RAW_TABLE)}"
            )
            row = cursor.fetchone() or {}
            return int(row.get("max_id") or 0)

    def fetch_all_raw(self) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {quote_identifier(RAW_TABLE)} ORDER BY source_listing_id")
            return list(cursor.fetchall())

    def fetch_cleaning_candidates(self, *, recheck_needs_review: bool = False) -> list[dict[str, Any]]:
        where = "checked=0"
        if recheck_needs_review:
            where = "checked=0 OR check_status='needs_review'"
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {quote_identifier(RAW_TABLE)} WHERE {where} ORDER BY source_listing_id"
            )
            return list(cursor.fetchall())

    def replace_model_catalog(self, catalog: dict[str, tuple[int, str]]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {quote_identifier(MODEL_CATALOG_TABLE)}")
            if catalog:
                cursor.executemany(
                    f"""
                    INSERT INTO {quote_identifier(MODEL_CATALOG_TABLE)}
                        (model_name_clean, observation_count, seed_source)
                    VALUES (%s, %s, %s)
                    """,
                    [(model, count, source) for model, (count, source) in sorted(catalog.items())],
                )

    def mark_raw(
        self,
        cursor,
        source_listing_id: int,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        cursor.execute(
            f"""
            UPDATE {quote_identifier(RAW_TABLE)}
            SET checked=1,
                check_status=%s,
                check_message=%s,
                checked_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE source_listing_id=%s
            """,
            (status, (message or "")[:1000] or None, source_listing_id),
        )

    def remove_cleaned(self, cursor, source_listing_id: int) -> None:
        cursor.execute(
            f"DELETE FROM {quote_identifier(CLEANED_TABLE)} WHERE source_listing_id=%s",
            (source_listing_id,),
        )

    def upsert_cleaned(self, cursor, row: dict[str, Any]) -> str:
        columns = tuple(row.keys())
        column_sql = ", ".join(quote_identifier(column) for column in columns)
        value_sql = ", ".join(["%s"] * len(columns))
        cursor.execute(
            f"SELECT id FROM {quote_identifier(CLEANED_TABLE)} WHERE source_listing_id=%s",
            (row["source_listing_id"],),
        )
        existing = cursor.fetchone()
        if existing:
            mutable_columns = [column for column in columns if column != "source_listing_id"]
            assignments = ", ".join(f"{quote_identifier(column)}=%s" for column in mutable_columns)
            try:
                cursor.execute(
                    f"""
                    UPDATE {quote_identifier(CLEANED_TABLE)}
                    SET {assignments}, updated_at=CURRENT_TIMESTAMP
                    WHERE source_listing_id=%s
                    """,
                    [row[column] for column in mutable_columns] + [row["source_listing_id"]],
                )
                return "updated"
            except pymysql.err.IntegrityError as error:
                if int(error.args[0]) != 1062:
                    raise
                # The revised source row now collides with another canonical row.
                # Raw CSV snapshots retain the revision; the derived stale clean row is removed.
                cursor.execute(
                    f"DELETE FROM {quote_identifier(CLEANED_TABLE)} WHERE source_listing_id=%s",
                    (row["source_listing_id"],),
                )
                return "duplicate"
        try:
            cursor.execute(
                f"INSERT INTO {quote_identifier(CLEANED_TABLE)} ({column_sql}) VALUES ({value_sql})",
                [row[column] for column in columns],
            )
            return "inserted"
        except pymysql.err.IntegrityError as error:
            if int(error.args[0]) == 1062:
                return "duplicate"
            raise

    def create_cleaning_run(self, started_at: dt.datetime) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {quote_identifier(CLEANING_RUNS_TABLE)} (started_at, status)
                VALUES (%s, 'running')
                """,
                (started_at,),
            )
            return int(cursor.lastrowid)

    def finish_cleaning_run(self, run_id: int, status: str, stats: dict[str, Any]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {quote_identifier(CLEANING_RUNS_TABLE)}
                SET completed_at=CURRENT_TIMESTAMP,
                    status=%s,
                    seed_model_count=%s,
                    processed_count=%s,
                    inserted_count=%s,
                    duplicate_count=%s,
                    review_count=%s,
                    rejected_count=%s,
                    metrics_json=%s
                WHERE id=%s
                """,
                (
                    status,
                    int(stats.get("seed_model_count", 0)),
                    int(stats.get("processed_count", 0)),
                    int(stats.get("inserted_count", 0)),
                    int(stats.get("duplicate_count", 0)),
                    int(stats.get("review_count", 0)),
                    int(stats.get("rejected_count", 0)),
                    json.dumps(stats, ensure_ascii=False, sort_keys=True),
                    run_id,
                ),
            )

    def cleaned_frame(self) -> pd.DataFrame:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {quote_identifier(CLEANED_TABLE)} ORDER BY id")
            return pd.DataFrame(list(cursor.fetchall()))

    def record_training_run(
        self,
        *,
        artifact_path: Path,
        best_model: str,
        train_rows: int,
        validation_rows: int,
        metrics: dict[str, Any],
    ) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {quote_identifier(TRAINING_RUNS_TABLE)}
                    (artifact_path, best_model, train_rows, validation_rows, metrics_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    str(artifact_path),
                    best_model,
                    train_rows,
                    validation_rows,
                    json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)


def chunks(values: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
