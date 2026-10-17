from __future__ import annotations

import argparse
import json
from pathlib import Path

from crawl.common import load_mysql_config, record_model_norm, mysql_connect
from crawl.international.purge import SOURCE_NAMES


def desired_model(record: dict) -> str | None:
    return record_model_norm(record)


def run(*, execute: bool = False, backup_path: Path | None = None, include_domestic_cat: bool = False) -> dict:
    config = load_mysql_config()
    placeholders = ", ".join(["%s"] * len(SOURCE_NAMES))
    cat_condition = """ OR manufacturer REGEXP '(^|[^a-z])(cat|caterpillar)($|[^a-z])|캐터필|카터필'
        OR model_name REGEXP '^CAT[ ._-]*[A-Z]{0,2}[0-9]'
        OR model_norm REGEXP '^CAT[ ._-]*[A-Z]{0,2}[0-9]'""" if include_domestic_cat else ""
    with mysql_connect(config, config.database) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                    SELECT id, model_name, listing_name, model_norm, manufacturer
                    FROM listings
                    WHERE source_site IN ({placeholders}) {cat_condition}
                """,
                SOURCE_NAMES,
            )
            rows = list(cursor.fetchall())
            changes = []
            for row in rows:
                normalized = desired_model(row)
                current = row.get("model_norm") or None
                if normalized != current:
                    changes.append((normalized, int(row["id"])))

            if execute and changes:
                if backup_path:
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    # Exclusive creation protects the previous rollback snapshot.
                    with backup_path.open("x", encoding="utf-8") as handle:
                        json.dump({"database":config.database,"rows":[{"id":row["id"],"model_norm":row["model_norm"]} for row in rows]}, handle,ensure_ascii=False)
                connection.begin()
                cursor.executemany(
                    "UPDATE listings SET model_norm=%s, updated_at=NOW() WHERE id=%s",
                    changes,
                )
                connection.commit()

    summary = {
        "database": config.database,
        "executed": execute,
        "matched": len(rows),
        "changed": len(changes),
        "cleared": sum(1 for value, _ in changes if value is None),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="국제 매물 모델명을 신뢰 사전으로 다시 정규화")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--backup-path", type=Path)
    parser.add_argument("--include-domestic-cat", action="store_true")
    args = parser.parse_args()
    run(execute=args.execute, backup_path=args.backup_path, include_domestic_cat=args.include_domestic_cat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
