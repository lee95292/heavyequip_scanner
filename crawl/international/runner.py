from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crawl.common import DEFAULT_CONFIG_PATH, KST, load_mysql_config, now_kst, parse_site_date, upsert_records
from crawl.international.catalog import source_by_slug
from crawl.international.source_http import (
    MASCUS_CATEGORIES,
    SourceAccessError,
    configure_proxy,
    fetch_machineryline,
    fetch_mascus,
    fetch_text,
    machineryline_url,
    mascus_url,
)
from crawl.international.parsers import parse_listing_payload
from crawl.international.sync import (
    claim_request,
    complete_request,
    fail_request,
    filter_new_stream_records,
    finalize_stream,
    plan_request,
    queue_planned_request,
    record_stream_items,
    recover_stale_requests,
    sync_progress,
)


SUPPORTED_SITES = ("machineryline", "mascus_global")
PROBE_ONLY_SITES = ("machinery_trader", "ironplanet", "rb_auction")
ALL_SITES = SUPPORTED_SITES + PROBE_ONLY_SITES


def _record_date(record: dict[str, Any]) -> dt.datetime | None:
    return parse_site_date(str(record.get("posted_at") or record.get("posted_date") or ""))


def _date_bounds(records: list[dict[str, Any]]) -> tuple[dt.datetime | None, dt.datetime | None]:
    dates = [value for value in (_record_date(record) for record in records) if value]
    return (max(dates), min(dates)) if dates else (None, None)


def _mysql_datetime(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(KST).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _run_page(
    config,
    *,
    site_slug: str,
    url: str,
    cursor: str,
    stream_key: str,
    cutoff: dt.datetime,
    remaining: int,
    fetcher,
) -> tuple[int, bool, bool]:
    """Return (saved items, has_next, page_was_already_complete)."""
    request = plan_request(site_slug, url=url, cursor=cursor, stream_key=stream_key)
    queue_planned_request(config, request, enqueue=False)
    if not claim_request(config, site_slug, request.request_fingerprint):
        return 0, True, True
    try:
        result = fetcher()
        parsed = [parse_listing_payload(site_slug, payload) for payload in result.payloads]
        recent_by_date = [record for record in parsed if (_record_date(record) or dt.datetime.min.replace(tzinfo=KST)) >= cutoff]
        recent = filter_new_stream_records(config, site_slug, stream_key, recent_by_date, remaining)
        upsert_records(config, recent)
        record_stream_items(config, site_slug, stream_key, recent)
        newest, oldest = _date_bounds(parsed)
        reached_cutoff = bool(parsed) and not recent_by_date and oldest is not None and oldest < cutoff
        has_next = result.has_next and not reached_cutoff and len(recent) < remaining
        reason = None
        if len(recent) >= remaining:
            reason = "item_limit"
            has_next = False
        elif reached_cutoff:
            reason = "date_cutoff"
        elif not result.has_next:
            reason = "source_exhausted"
        complete_request(
            config,
            request,
            response_status=result.status,
            item_count=len(recent),
            # Stream completion is decided by the runner after all category/page
            # branches finish. Keeping it planned here makes mid-run restarts safe.
            next_cursor="pending",
            newest_seen_at=_mysql_datetime(newest),
            oldest_seen_at=_mysql_datetime(oldest),
            stop_reason=reason,
        )
        return len(recent), has_next, False
    except Exception as error:
        fail_request(config, request, error)
        raise


def run_machineryline(config, stream_key: str, cutoff: dt.datetime, limit: int, sleep_seconds: float) -> dict:
    progress = sync_progress(config, "machineryline", stream_key)
    total = int(progress.get("item_count") or 0)
    if progress.get("status") == "complete":
        return {"site": "machineryline", "items": total, "requests": 0, "status": "complete", "resumed": True}
    page = 1
    requests = 0
    while total < limit:
        url = machineryline_url(page)
        saved, has_next, skipped = _run_page(
            config,
            site_slug="machineryline",
            url=url,
            cursor=f"page:{page}",
            stream_key=stream_key,
            cutoff=cutoff,
            remaining=limit - total,
            fetcher=lambda page=page: fetch_machineryline(page),
        )
        total += saved
        requests += 0 if skipped else 1
        if not has_next or total >= limit:
            break
        page += 1
        if not skipped:
            time.sleep(max(0.0, sleep_seconds))
    finalize_stream(config, "machineryline", stream_key, "item_limit" if total >= limit else "date_or_source_exhausted")
    return {"site": "machineryline", "items": total, "requests": requests, "status": "complete"}


def run_mascus(config, stream_key: str, cutoff: dt.datetime, limit: int, sleep_seconds: float) -> dict:
    progress = sync_progress(config, "mascus_global", stream_key)
    total = int(progress.get("item_count") or 0)
    if progress.get("status") == "complete":
        return {"site": "mascus_global", "items": total, "requests": 0, "status": "complete", "resumed": True}
    active = {category: 1 for category in MASCUS_CATEGORIES}
    requests = 0
    successful_pages = 0
    errors: list[str] = []
    while active and total < limit:
        for category, page in list(active.items()):
            url = mascus_url(category, page)
            try:
                saved, has_next, skipped = _run_page(
                    config,
                    site_slug="mascus_global",
                    url=url,
                    cursor=f"{category}:{page}",
                    stream_key=stream_key,
                    cutoff=cutoff,
                    remaining=limit - total,
                    fetcher=lambda category=category, page=page: fetch_mascus(category, page),
                )
            except SourceAccessError as error:
                errors.append(f"{category}: {error}")
                del active[category]
                continue
            successful_pages += 0 if skipped else 1
            total += saved
            requests += 0 if skipped else 1
            if not has_next or total >= limit:
                del active[category]
            else:
                active[category] = page + 1
            if not skipped:
                time.sleep(max(0.0, sleep_seconds))
            if total >= limit:
                break
    if successful_pages == 0 and errors:
        raise SourceAccessError(f"all Mascus categories failed; first error: {errors[0]}")
    finalize_stream(config, "mascus_global", stream_key, "item_limit" if total >= limit else "date_or_source_exhausted")
    return {
        "site": "mascus_global", "items": total, "requests": requests, "status": "complete",
        "categoryErrors": len(errors),
    }


def run_probe(config, site_slug: str, stream_key: str) -> dict:
    source = source_by_slug(site_slug)
    request = plan_request(site_slug, url=source["listingUrl"], cursor="probe:1", stream_key=stream_key)
    queue_planned_request(config, request, enqueue=False)
    if not claim_request(config, site_slug, request.request_fingerprint):
        progress = sync_progress(config, site_slug, stream_key)
        return {"site": site_slug, "status": progress.get("status") or "unchanged", "error": progress.get("last_error")}
    try:
        status, _, _ = fetch_text(source["listingUrl"])
        error = SourceAccessError("public listing responded but no stable parser is enabled", status=status)
        fail_request(config, request, error)
        return {"site": site_slug, "status": "blocked", "error": str(error)}
    except Exception as error:
        fail_request(config, request, error)
        return {"site": site_slug, "status": "blocked", "error": str(error)}


def run(
    *, config_path: Path, mode: str, sites: list[str], days: int, limit: int,
    sleep_seconds: float, stream_key_override: str | None = None,
) -> dict:
    config = load_mysql_config(config_path)
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        raw_config = {}
    international = raw_config.get("international") if isinstance(raw_config, dict) else {}
    proxy_url = (
        international.get("http_proxy") if isinstance(international, dict) else None
    ) or os.environ.get("INTERNATIONAL_HTTP_PROXY", "")
    configure_proxy(str(proxy_url))
    recover_stale_requests(config)
    now = now_kst()
    stream_key = stream_key_override or (
        "backfill:2026-09-18" if mode == "backfill" else f"daily:{now.date().isoformat()}"
    )
    cutoff = now - dt.timedelta(days=days if mode == "backfill" else 1)
    summaries: list[dict[str, Any]] = []
    for site_slug in sites:
        try:
            if site_slug == "machineryline":
                summaries.append(run_machineryline(config, stream_key, cutoff, limit, sleep_seconds))
            elif site_slug == "mascus_global":
                summaries.append(run_mascus(config, stream_key, cutoff, limit, sleep_seconds))
            else:
                summaries.append(run_probe(config, site_slug, stream_key))
        except Exception as error:
            summaries.append({"site": site_slug, "status": "failed", "error": str(error)})
    return {
        "mode": mode,
        "streamKey": stream_key,
        "cutoff": cutoff.isoformat(),
        "limitPerSite": limit,
        "sites": summaries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="국제 중장비 매물 동기화")
    parser.add_argument("--mode", choices=("backfill", "daily"), default="daily")
    parser.add_argument("--site", action="append", choices=ALL_SITES, dest="sites")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--sleep", type=float, default=1.5)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--stream-key", help="검증 실행 등에서 사용할 별도 체크포인트 키")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(
        config_path=args.config,
        mode=args.mode,
        sites=args.sites or list(ALL_SITES),
        days=max(1, args.days),
        limit=max(1, args.limit),
        sleep_seconds=max(0.0, args.sleep),
        stream_key_override=args.stream_key,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if all(site.get("status") != "failed" for site in summary["sites"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
