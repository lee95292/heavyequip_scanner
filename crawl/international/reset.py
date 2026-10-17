from __future__ import annotations

import argparse
import datetime as dt
import decimal
import gzip
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crawl.common import DATA_DIR, DEFAULT_CONFIG_PATH, load_mysql_config, mysql_connect
from crawl.international.runner import ALL_SITES
from crawl.international.parsers import SOURCE_NAMES


INTERNATIONAL_SOURCE_NAMES = tuple(SOURCE_NAMES[slug] for slug in ALL_SITES)
DEFAULT_BACKUP_DIR = DATA_DIR / "backups"


def _json_default(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    raise TypeError(f"unsupported backup value: {type(value).__name__}")


def table_exists(cursor, database: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
        """,
        (database, table),
    )
    return bool(int(cursor.fetchone()["cnt"] or 0))


def reset_international(config_path: Path, backup_dir: Path, execute: bool) -> dict[str, Any]:
    config = load_mysql_config(config_path)
    placeholders_names = ",".join(["%s"] * len(INTERNATIONAL_SOURCE_NAMES))
    placeholders_slugs = ",".join(["%s"] * len(ALL_SITES))
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"international_listings_{stamp}.jsonl.gz"
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS cnt FROM listings WHERE source_site IN ({placeholders_names})",
                INTERNATIONAL_SOURCE_NAMES,
            )
            listing_count = int(cursor.fetchone()["cnt"] or 0)
            counts: dict[str, int] = {"listings": listing_count}
            for table in ("source_sync_state", "source_request_log", "source_sync_item", "crawl_tasks"):
                if not table_exists(cursor, config.database, table):
                    counts[table] = 0
                    continue
                cursor.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table} WHERE site_slug IN ({placeholders_slugs})",
                    ALL_SITES,
                )
                counts[table] = int(cursor.fetchone()["cnt"] or 0)
            if not execute:
                return {"execute": False, "counts": counts, "backup_path": str(backup_path)}

            backup_dir.mkdir(parents=True, exist_ok=True)
            cursor.execute(
                f"SELECT * FROM listings WHERE source_site IN ({placeholders_names}) ORDER BY id",
                INTERNATIONAL_SOURCE_NAMES,
            )
            with gzip.open(backup_path, "wt", encoding="utf-8") as handle:
                while True:
                    rows = cursor.fetchmany(500)
                    if not rows:
                        break
                    for row in rows:
                        handle.write(json.dumps(row, ensure_ascii=False, default=_json_default, sort_keys=True) + "\n")

            conn.begin()
            try:
                if table_exists(cursor, config.database, "listing_model_matches"):
                    cursor.execute(
                        f"""
                        DELETE match_row FROM listing_model_matches AS match_row
                        JOIN listings AS listing ON listing.id=match_row.listing_id
                        WHERE listing.source_site IN ({placeholders_names})
                        """,
                        INTERNATIONAL_SOURCE_NAMES,
                    )
                cursor.execute(
                    f"DELETE FROM listings WHERE source_site IN ({placeholders_names})",
                    INTERNATIONAL_SOURCE_NAMES,
                )
                for table in ("source_sync_item", "source_request_log", "source_sync_state", "crawl_tasks"):
                    if table_exists(cursor, config.database, table):
                        cursor.execute(
                            f"DELETE FROM {table} WHERE site_slug IN ({placeholders_slugs})",
                            ALL_SITES,
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    return {"execute": True, "counts": counts, "backup_path": str(backup_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="국제 매물과 국제 동기화 체크포인트를 백업 후 초기화")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--execute", action="store_true", help="생략 시 삭제 없이 대상 개수만 출력")
    args = parser.parse_args(argv)
    print(json.dumps(reset_international(args.config, args.backup_dir, args.execute), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
