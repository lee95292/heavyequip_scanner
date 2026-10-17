from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crawl.common import DEFAULT_CONFIG_PATH, load_mysql_config, mysql_connect
from crawl.international.catalog import load_source_catalog


SOURCE_NAMES = tuple(source['name'] for source in load_source_catalog()['sources'])
SITE_SLUGS = tuple(source['slug'] for source in load_source_catalog()['sources'])
STATE_TABLES = ("source_sync_item", "source_request_log", "source_sync_state", "crawl_tasks")


def _placeholders(values: tuple[str, ...]) -> str:
    return ", ".join(["%s"] * len(values))


def purge(config_path: Path, *, execute: bool) -> dict:
    config = load_mysql_config(config_path)
    counts: dict[str, int] = {}
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS cnt FROM listings WHERE source_site IN ({_placeholders(SOURCE_NAMES)})",
                SOURCE_NAMES,
            )
            counts["listings"] = int(cursor.fetchone()["cnt"])
            for table in STATE_TABLES:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                    """,
                    (config.database, table),
                )
                if not int(cursor.fetchone()["cnt"]):
                    counts[table] = 0
                    continue
                cursor.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table} WHERE site_slug IN ({_placeholders(SITE_SLUGS)})",
                    SITE_SLUGS,
                )
                counts[table] = int(cursor.fetchone()["cnt"])

            if not execute:
                return {"executed": False, "database": config.database, "matched": counts}

            conn.begin()
            try:
                cursor.execute(
                    f"DELETE FROM listings WHERE source_site IN ({_placeholders(SOURCE_NAMES)})",
                    SOURCE_NAMES,
                )
                for table in STATE_TABLES:
                    if counts[table]:
                        cursor.execute(
                            f"DELETE FROM {table} WHERE site_slug IN ({_placeholders(SITE_SLUGS)})",
                            SITE_SLUGS,
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    return {"executed": True, "database": config.database, "deleted": counts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="국제 매물과 해당 동기화 상태만 삭제")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--execute", action="store_true", help="없으면 삭제 대상 건수만 출력")
    args = parser.parse_args(argv)
    print(json.dumps(purge(args.config, execute=args.execute), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
