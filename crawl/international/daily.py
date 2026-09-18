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
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crawl.common import DATA_DIR, DEFAULT_CONFIG_PATH, KST, now_kst
from crawl.international.runner import ALL_SITES, run


DEFAULT_STATE = DATA_DIR / "international_daily_state.json"
DEFAULT_LOCK = DATA_DIR / "international_daily.lock"


def parse_daily_at(value: str) -> tuple[int, int]:
    try:
        hour, minute = (int(part) for part in value.split(":", 1))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("daily time must use HH:MM") from error
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("daily time must use HH:MM")
    return hour, minute


def read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def write_success_state_safely(path: Path, summary: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps({
            "last_success_date": now_kst().date().isoformat(),
            "last_success_at": now_kst().isoformat(),
            "summary": summary,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return True
    except OSError as error:
        print(f"[international-daily] state write failed: {error}", file=sys.stderr)
        return False


def acquire_process_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def next_due_run(now: dt.datetime, daily_at: tuple[int, int], last_success_date: str) -> dt.datetime:
    now = now.astimezone(KST)
    scheduled = now.replace(hour=daily_at[0], minute=daily_at[1], second=0, microsecond=0)
    if last_success_date == now.date().isoformat():
        return scheduled + dt.timedelta(days=1)
    return now if now >= scheduled else scheduled


def wait_until(target: dt.datetime) -> None:
    while True:
        remaining = (target - now_kst()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 60))


def execute(config: Path, sleep_seconds: float) -> dict:
    summary = run(
        config_path=config,
        mode="daily",
        sites=list(ALL_SITES),
        days=1,
        limit=5000,
        sleep_seconds=sleep_seconds,
        stream_key_override=None,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def successful(summary: dict) -> bool:
    supported = {site["site"]: site for site in summary.get("sites", []) if site.get("site") in {"machineryline", "mascus_global"}}
    return len(supported) == 2 and all(site.get("status") == "complete" for site in supported.values())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="국제 매물 매일 수집 워커")
    parser.add_argument("--at", default=os.environ.get("INTERNATIONAL_DAILY_AT", "05:00"))
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("CRAWL_CONFIG_PATH", DEFAULT_CONFIG_PATH)))
    parser.add_argument("--sleep", type=float, default=float(os.environ.get("INTERNATIONAL_CRAWL_SLEEP", "1.5")))
    parser.add_argument("--state-path", type=Path, default=Path(os.environ.get("INTERNATIONAL_DAILY_STATE_PATH", DEFAULT_STATE)))
    parser.add_argument("--lock-path", type=Path, default=Path(os.environ.get("INTERNATIONAL_DAILY_LOCK_PATH", DEFAULT_LOCK)))
    parser.add_argument("--run-once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    daily_at = parse_daily_at(args.at)
    lock = acquire_process_lock(args.lock_path)
    if lock is None:
        print(f"[international-daily] lock already held: {args.lock_path}", file=sys.stderr)
        return 2
    try:
        if args.run_once:
            summary = execute(args.config, max(0.0, args.sleep))
            return 0 if successful(summary) and write_success_state_safely(args.state_path, summary) else 1
        while True:
            state = read_state(args.state_path)
            due = next_due_run(now_kst(), daily_at, str(state.get("last_success_date") or ""))
            print(f"[international-daily] next run={due.isoformat()}")
            wait_until(due)
            try:
                summary = execute(args.config, max(0.0, args.sleep))
            except Exception as error:
                print(f"[international-daily] failed: {type(error).__name__}: {error}", file=sys.stderr)
                time.sleep(900)
                continue
            if successful(summary):
                write_success_state_safely(args.state_path, summary)
            else:
                time.sleep(900)
    finally:
        lock.close()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
