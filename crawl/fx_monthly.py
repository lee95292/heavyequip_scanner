from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import signal
import sys
import time
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.common import DATA_DIR, DEFAULT_CONFIG_PATH, KST, ensure_database, load_mysql_config, mysql_connect, now_kst
from crawl.fx_rates import FX_CACHE_PATH, FxSnapshot, refresh_or_cached, sale_price_fields


DEFAULT_STATE = DATA_DIR / "fx_monthly_state.json"
DEFAULT_LOCK = DATA_DIR / "fx_monthly.lock"


def parse_at(value: str) -> tuple[int, int]:
    try:
        hour, minute = (int(part) for part in value.split(":", 1))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("monthly time must use HH:MM") from error
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("monthly time must use HH:MM")
    return hour, minute


def next_due_run(now: dt.datetime, day: int, at: tuple[int, int], last_success_month: str) -> dt.datetime:
    now = now.astimezone(KST)
    this_month = now.strftime("%Y-%m")
    if last_success_month != this_month:
        return now
    year = now.year + (1 if now.month == 12 else 0)
    month = 1 if now.month == 12 else now.month + 1
    return dt.datetime(year, month, day, at[0], at[1], tzinfo=KST)


def read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def write_state(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({
        "last_success_month": now_kst().strftime("%Y-%m"),
        "last_success_at": now_kst().isoformat(),
        "summary": summary,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def acquire_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def update_all_prices(config_path: Path, snapshot: FxSnapshot, batch_size: int = 5000) -> dict[str, int | str]:
    config = load_mysql_config(config_path)
    ensure_database(config)
    last_id = scanned = updated = converted = missing_currency = missing_rate = 0
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMPORARY TABLE fx_update_batch (
                    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
                    sale_currency CHAR(3) NULL,
                    sale_amount DECIMAL(20,4) NULL,
                    sale_fx_rate_krw DECIMAL(20,8) NULL,
                    sale_fx_rate_date DATE NULL,
                    price_krw BIGINT NULL
                ) ENGINE=InnoDB
                """
            )
        while True:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, source_site, price, price_krw, sale_currency, sale_amount, raw_json
                    FROM listings WHERE id > %s ORDER BY id LIMIT %s
                    """,
                    (last_id, batch_size),
                )
                rows = cursor.fetchall()
                if not rows:
                    break
                changes = []
                for row in rows:
                    last_id = int(row["id"])
                    scanned += 1
                    fields = sale_price_fields({**row, "raw": row.get("raw_json")}, snapshot)
                    if not fields["sale_currency"]:
                        missing_currency += 1
                    elif fields["sale_fx_rate_krw"] is None:
                        missing_rate += 1
                    if fields["price_krw"] is not None:
                        converted += 1
                    changes.append((
                        fields["sale_currency"], fields["sale_amount"], fields["sale_fx_rate_krw"],
                        fields["sale_fx_rate_date"], fields["price_krw"], last_id,
                    ))
                cursor.execute("TRUNCATE TABLE fx_update_batch")
                cursor.executemany(
                    """
                    INSERT INTO fx_update_batch
                        (sale_currency, sale_amount, sale_fx_rate_krw, sale_fx_rate_date, price_krw, id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    changes,
                )
                cursor.execute(
                    """
                    UPDATE listings AS listing
                    JOIN fx_update_batch AS batch ON batch.id=listing.id
                    SET listing.sale_currency=batch.sale_currency,
                        listing.sale_amount=batch.sale_amount,
                        listing.sale_fx_rate_krw=batch.sale_fx_rate_krw,
                        listing.sale_fx_rate_date=batch.sale_fx_rate_date,
                        listing.price_krw=batch.price_krw
                    """
                )
                updated += len(changes)
            print(f"[fx-monthly] scanned={scanned} updated={updated} last_id={last_id}")
    return {
        "rate_date": snapshot.rate_date,
        "scanned": scanned,
        "updated": updated,
        "converted": converted,
        "missing_currency": missing_currency,
        "missing_rate": missing_rate,
    }


def execute(config_path: Path, cache_path: Path, batch_size: int) -> dict:
    snapshot, refreshed, refresh_error = refresh_or_cached(cache_path)
    summary = update_all_prices(config_path, snapshot, batch_size)
    summary.update({"refreshed": refreshed, "refresh_error": refresh_error or "", "source": snapshot.source_url})
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="월 1회 전체 매물 환율 및 원화 계산값 보정")
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("CRAWL_CONFIG_PATH", DEFAULT_CONFIG_PATH)))
    parser.add_argument("--cache-path", type=Path, default=Path(os.environ.get("FX_CACHE_PATH", FX_CACHE_PATH)))
    parser.add_argument("--state-path", type=Path, default=Path(os.environ.get("FX_MONTHLY_STATE_PATH", DEFAULT_STATE)))
    parser.add_argument("--lock-path", type=Path, default=Path(os.environ.get("FX_MONTHLY_LOCK_PATH", DEFAULT_LOCK)))
    parser.add_argument("--day", type=int, default=int(os.environ.get("FX_MONTHLY_DAY", "1")))
    parser.add_argument("--at", default=os.environ.get("FX_MONTHLY_AT", "05:30"))
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--run-once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    day = max(1, min(28, args.day))
    at = parse_at(args.at)
    batch_size = max(100, min(10000, args.batch_size))
    lock = acquire_lock(args.lock_path)
    if lock is None:
        print(f"[fx-monthly] lock already held: {args.lock_path}", file=sys.stderr)
        return 2
    try:
        if args.run_once:
            summary = execute(args.config, args.cache_path, batch_size)
            write_state(args.state_path, summary)
            return 0
        while True:
            state = read_state(args.state_path)
            due = next_due_run(now_kst(), day, at, str(state.get("last_success_month") or ""))
            print(f"[fx-monthly] next run={due.isoformat()}")
            while (due - now_kst()).total_seconds() > 0:
                time.sleep(min(60, max(1, (due - now_kst()).total_seconds())))
            try:
                summary = execute(args.config, args.cache_path, batch_size)
                write_state(args.state_path, summary)
            except Exception as error:
                print(f"[fx-monthly] failed: {type(error).__name__}: {error}", file=sys.stderr)
                time.sleep(900)
    finally:
        lock.close()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
