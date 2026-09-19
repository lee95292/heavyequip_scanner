from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.common import (
    DEFAULT_CONFIG_PATH,
    clean_text,
    load_mysql_config,
    model_manufacturer,
    model_norm,
    mysql_connect,
)


def backfill(config_path: Path, batch_size: int) -> dict[str, int]:
    config = load_mysql_config(config_path)
    last_id = 0
    scanned = updated = filled_model = filled_manufacturer = 0
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMPORARY TABLE model_norm_backfill_batch (
                    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
                    model_name VARCHAR(255) NOT NULL,
                    model_norm VARCHAR(255) NOT NULL,
                    manufacturer VARCHAR(255) NULL
                ) ENGINE=InnoDB
                """
            )
        while True:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, listing_name, model_name, model_norm, manufacturer
                    FROM listings WHERE id > %s ORDER BY id LIMIT %s
                    """,
                    (last_id, batch_size),
                )
                rows = cursor.fetchall()
                if not rows:
                    break
                changes: list[tuple[str, str, str | None, int]] = []
                for row in rows:
                    last_id = int(row["id"])
                    scanned += 1
                    canonical = model_norm(row.get("model_name")) or model_norm(row.get("listing_name"))
                    if not canonical:
                        continue
                    manufacturer = clean_text(row.get("manufacturer")) or model_manufacturer(canonical)
                    if (
                        clean_text(row.get("model_name")) == canonical
                        and clean_text(row.get("model_norm")) == canonical
                        and clean_text(row.get("manufacturer")) == clean_text(manufacturer)
                    ):
                        continue
                    if not clean_text(row.get("model_name")):
                        filled_model += 1
                    if not clean_text(row.get("manufacturer")) and manufacturer:
                        filled_manufacturer += 1
                    changes.append((canonical, canonical, manufacturer or None, last_id))
                if changes:
                    cursor.execute("TRUNCATE TABLE model_norm_backfill_batch")
                    cursor.executemany(
                        """
                        INSERT INTO model_norm_backfill_batch (model_name, model_norm, manufacturer, id)
                        VALUES (%s, %s, %s, %s)
                        """,
                        changes,
                    )
                    cursor.execute(
                        """
                        UPDATE listings AS listing
                        JOIN model_norm_backfill_batch AS batch ON batch.id = listing.id
                        SET listing.model_name=batch.model_name,
                            listing.model_norm=batch.model_norm,
                            listing.manufacturer=batch.manufacturer
                        """
                    )
                    updated += len(changes)
            print(f"[model-backfill] scanned={scanned} updated={updated} last_id={last_id}")
    return {
        "scanned": scanned,
        "updated": updated,
        "filled_model": filled_model,
        "filled_manufacturer": filled_manufacturer,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="기존 매물 모델명을 정규화 카탈로그로 일괄 보정")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args(argv)
    print(backfill(args.config, max(100, min(args.batch_size, 10000))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
