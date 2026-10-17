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

from crawl.common import DEFAULT_CONFIG_PATH, KST, ensure_database, mysql_connect, load_mysql_config, now_kst, parse_site_date, upsert_records
from crawl.international.catalog import source_by_slug
from crawl.international.catalog import load_source_catalog
from crawl.international.marketplaces import PayloadCache, plant_url, fetch_plant, EUROPE_CATEGORIES, europe_url, fetch_europe
from crawl.international.source_http import (
    MASCUS_CATEGORIES,
    SourceAccessError,
    configure_proxy,
    fetch_machineryline,
    fetch_mascus,
    fetch_text,
    machineryline_url,
    mascus_url,
    inspect_ironplanet,
    IRONPLANET_PRICE_FILTERS, ironplanet_url, fetch_ironplanet,
)
from crawl.international.parsers import parse_listing_payload
from crawl.international.policy import InternationalPolicy, filter_eligible_records, load_policy
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
    cached_page_has_next,
    prepare_extension,
)


IMPLEMENTED_SITES = ('machineryline','mascus_global','ironplanet','plant_equipment','europe_construction')
SUPPORTED_SITES = tuple(s for s in IMPLEMENTED_SITES if source_by_slug(s)['readiness']=='collection_enabled')
PROBE_ONLY_SITES = ('machinery_trader','rb_auction','truck1')
ALL_SITES = IMPLEMENTED_SITES + PROBE_ONLY_SITES


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
    policy: InternationalPolicy,
    fetcher,
    only_new_listings: bool = False,
    allow_undated: bool = False,
) -> tuple[int, bool, bool]:
    """Return (saved items, has_next, page_was_already_complete)."""
    request = plan_request(site_slug, url=url, cursor=cursor, stream_key=stream_key)
    queue_planned_request(config, request, enqueue=False)
    if not claim_request(config, site_slug, request.request_fingerprint):
        return 0, cached_page_has_next(config, request), True
    try:
        result = fetcher()
        parsed = [parse_listing_payload(site_slug, payload) for payload in result.payloads]
        eligible, rejected = filter_eligible_records(parsed, policy)
        if rejected:
            print(f"[international] {site_slug} rejected={json.dumps(rejected, sort_keys=True)}")
        recent_by_date = [
            record for record in eligible
            if (allow_undated and _record_date(record) is None)
            or (_record_date(record) or dt.datetime.min.replace(tzinfo=KST)) >= cutoff
        ]
        recent = filter_new_stream_records(config, site_slug, stream_key, recent_by_date, remaining,
                                           only_new_listings=only_new_listings)
        newest, oldest = _date_bounds(parsed)
        # A page of unpriced/rejected machines is not proof we reached old data.
        # Stop only when every dated source record is older than the cutoff.
        reached_cutoff = bool(parsed) and all(_record_date(record) is not None and _record_date(record) < cutoff for record in parsed)
        has_next = result.has_next and not reached_cutoff and len(recent) < remaining
        reason = None
        if len(recent) >= remaining:
            reason = "item_limit"
            has_next = False
        elif reached_cutoff:
            reason = "date_cutoff"
        elif not result.has_next:
            reason = "source_exhausted"
        with mysql_connect(config, config.database) as connection:
            connection.begin()
            try:
                upsert_records(config, recent, connection=connection)
                record_stream_items(config, site_slug, stream_key, recent, connection=connection)
                committed = complete_request(
                    config, request, response_status=result.status, item_count=len(recent),
                    next_cursor="pending", newest_seen_at=_mysql_datetime(newest),
                    oldest_seen_at=_mysql_datetime(oldest), stop_reason=reason,
                    # A local item cap must not turn a resumable page into a
                    # terminal source page when a later expansion is approved.
                    has_next=result.has_next and not reached_cutoff, connection=connection,
                )
                if not committed:
                    raise RuntimeError("request claim changed before page commit")
            except Exception:
                connection.rollback()
                raise
        print(f"[international] {site_slug} cursor={cursor} saved={len(recent)} next={has_next}", flush=True)
        return len(recent), has_next, False
    except Exception as error:
        fail_request(config, request, error)
        raise


def run_ironplanet(config, stream_key, cutoff, limit, sleep_seconds, policy, only_new_listings=False):
    """Current priced inventory; explicitly approved exception to registration age."""
    return run_segmented_source(config, 'ironplanet', IRONPLANET_PRICE_FILTERS,
                                ironplanet_url, fetch_ironplanet, stream_key, cutoff,
                                min(limit, 8000), sleep_seconds, policy, only_new_listings,
                                allow_undated=True)


def run_segmented_source(config, site_slug, segments, url_builder, fetcher, stream_key,
                         cutoff, limit, sleep_seconds, policy, only_new_listings=False,
                         allow_undated=False):
    progress = sync_progress(config, site_slug, stream_key)
    total = int(progress.get('item_count') or 0)
    if progress.get('status') == 'complete':
        return {'site':site_slug, 'items':total, 'requests':0, 'status':'complete', 'resumed':True}
    active = {segment:1 for segment in segments}
    requests = 0
    errors = []
    access_blocks = []
    while active and total < limit:
        for segment, page in list(active.items()):
            try:
                saved, has_next, skipped = _run_page(
                    config, site_slug=site_slug, url=url_builder(segment,page),
                    cursor=f'{segment}:{page}', stream_key=stream_key, cutoff=cutoff,
                    remaining=limit-total, policy=policy, fetcher=lambda:fetcher(segment,page),
                    only_new_listings=only_new_listings, allow_undated=allow_undated)
                total += saved
                requests += int(not skipped)
                if has_next and page >= 500:
                    raise SourceAccessError('pagination safety limit reached; checkpoint retained')
                if not has_next:
                    del active[segment]
                else:
                    active[segment] = page+1
                if not skipped:
                    time.sleep(max(0,sleep_seconds))
            except SourceAccessError as error:
                errors.append(f'{segment}:{page}: {error}')
                access_blocks.append(error.status in (202,403,429))
                del active[segment]
                if access_blocks[-1]:
                    active.clear()
                    break
            if total >= limit:
                break
    complete = not errors or total >= limit
    if complete:
        finalize_stream(config,site_slug,stream_key,'item_limit' if total>=limit else 'source_exhausted')
    return {'site':site_slug,'items':total,'requests':requests,
            'status':'complete' if complete else ('blocked' if access_blocks and all(access_blocks) else 'failed'),'segmentErrors':errors,
            'registrationDatePolicy':'current_inventory_undated_allowed' if allow_undated else 'recent_year'}


def run_machineryline(
    config, stream_key: str, cutoff: dt.datetime, limit: int, sleep_seconds: float,
    policy: InternationalPolicy, only_new_listings: bool = False,
) -> dict:
    progress = sync_progress(config, "machineryline", stream_key)
    total = int(progress.get("item_count") or 0)
    if progress.get("status") == "complete":
        return {"site": "machineryline", "items": total, "requests": 0, "status": "complete", "resumed": True}
    page = 1
    requests = 0
    minimum_price_eur = policy.source_minimum("EUR")
    while total < limit:
        url = machineryline_url(page, minimum_price_eur)
        saved, has_next, skipped = _run_page(
            config,
            site_slug="machineryline",
            url=url,
            cursor=f"page:{page}",
            stream_key=stream_key,
            cutoff=cutoff,
            remaining=limit - total,
            policy=policy,
            fetcher=lambda page=page: fetch_machineryline(page, minimum_price_eur),
            only_new_listings=only_new_listings,
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


def run_mascus(
    config, stream_key: str, cutoff: dt.datetime, limit: int, sleep_seconds: float,
    policy: InternationalPolicy, only_new_listings: bool = False,
) -> dict:
    progress = sync_progress(config, "mascus_global", stream_key)
    total = int(progress.get("item_count") or 0)
    if progress.get("status") == "complete":
        return {"site": "mascus_global", "items": total, "requests": 0, "status": "complete", "resumed": True}
    active = {category: 1 for category in MASCUS_CATEGORIES}
    requests = 0
    successful_pages = 0
    errors: list[str] = []
    attempts: dict[str, int] = {}
    minimum_price_usd = policy.source_minimum("USD")
    while active and total < limit:
        for category, page in list(active.items()):
            url = mascus_url(category, page, minimum_price_usd)
            try:
                saved, has_next, skipped = _run_page(
                    config,
                    site_slug="mascus_global",
                    url=url,
                    cursor=f"{category}:{page}",
                    stream_key=stream_key,
                    cutoff=cutoff,
                    remaining=limit - total,
                    policy=policy,
                    fetcher=lambda category=category, page=page: fetch_mascus(
                        category, page, minimum_price_usd
                    ),
                    only_new_listings=only_new_listings,
                )
            except SourceAccessError as error:
                attempts[category] = attempts.get(category, 0) + 1
                if error.status in (429, 502, 503, 504, None) and attempts[category] < 3:
                    time.sleep(max(3.0, sleep_seconds) * attempts[category])
                    continue
                errors.append(f"{category}: {error}")
                del active[category]
                continue
            attempts[category] = 0
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
    if not errors or total >= limit:
        finalize_stream(config, "mascus_global", stream_key, "item_limit" if total >= limit else "date_or_source_exhausted")
    return {
        "site": "mascus_global", "items": total, "requests": requests,
        "status": "complete" if not errors or total >= limit else "failed",
        "categoryErrors": errors,
    }


def run_probe(config, site_slug: str, stream_key: str) -> dict:
    source = source_by_slug(site_slug)
    request = plan_request(site_slug, url=source["listingUrl"], cursor="probe:1", stream_key=stream_key)
    queue_planned_request(config, request, enqueue=False)
    if not claim_request(config, site_slug, request.request_fingerprint):
        progress = sync_progress(config, site_slug, stream_key)
        return {"site": site_slug, "status": progress.get("status") or "unchanged", "error": progress.get("last_error")}
    try:
        if site_slug == "ironplanet":
            evidence = inspect_ironplanet()
            error = SourceAccessError(evidence["reason"], status=evidence["httpStatus"])
            fail_request(config, request, error)
            return {"site":site_slug, **evidence}
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
    extend_by: int = 0, expansion_key: str | None = None,
) -> dict:
    config = load_mysql_config(config_path)
    ensure_database(config)
    if extend_by and (mode != "backfill" or not expansion_key):
        raise ValueError("--extend-by requires --mode backfill and a stable --expansion-key")
    policy = load_policy(config_path)
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
        "backfill:construction-priced-v1" if mode == "backfill" else f"daily:{now.date().isoformat()}"
    )
    cutoff = now - dt.timedelta(days=days if mode == "backfill" else 1)
    summaries: list[dict[str, Any]] = []
    for site_slug in sites:
        source = source_by_slug(site_slug)
        if site_slug in IMPLEMENTED_SITES and site_slug not in SUPPORTED_SITES:
            summaries.append({'site':site_slug,'status':'awaiting_date_policy','items':0,
                              'error':'등록일 미상 매물 수집 정책 승인 대기. 등록일을 임의로 만들지 않습니다.'})
            continue
        lock_connection = mysql_connect(config, config.database)
        try:
            with lock_connection.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, 0) AS acquired", (f"scanner:international:{site_slug}",))
                if not int(cursor.fetchone()["acquired"] or 0):
                    summaries.append({"site":site_slug,"status":"failed","error":"another collector owns this site; retry later"})
                    continue
            site_limit, site_cutoff = limit, cutoff
            plan = None
            if extend_by and site_slug in SUPPORTED_SITES:
                plan = prepare_extension(config, site_slug, stream_key, expansion_key, extend_by, _mysql_datetime(cutoff))
                site_limit = int(plan["target_count"])
                site_cutoff = parse_site_date(str(plan["cutoff_at"]))
            if site_slug == "machineryline":
                summaries.append(run_machineryline(config, stream_key, site_cutoff, site_limit, sleep_seconds, policy, bool(extend_by)))
            elif site_slug == "mascus_global":
                summaries.append(run_mascus(config, stream_key, site_cutoff, site_limit, sleep_seconds, policy, bool(extend_by)))
            elif site_slug == 'ironplanet':
                summaries.append(run_ironplanet(config, stream_key, site_cutoff, site_limit, sleep_seconds, policy, bool(extend_by)))
            elif site_slug in ('plant_equipment','europe_construction'):
                cache = PayloadCache(config,site_slug,stream_key,sleep_seconds)
                if site_slug == 'plant_equipment':
                    minimum = policy.source_minimum('USD')
                    segments = ('construction',)
                    url_builder = lambda segment,page:plant_url(segment,page,minimum)
                    fetcher = lambda segment,page:fetch_plant(segment,page,minimum,cache)
                else:
                    segments = tuple(EUROPE_CATEGORIES)
                    url_builder = europe_url
                    fetcher = lambda segment,page:fetch_europe(segment,page,cache)
                summaries.append(run_segmented_source(config,site_slug,segments,url_builder,fetcher,
                    stream_key,site_cutoff,min(site_limit,8000),sleep_seconds,policy,bool(extend_by),
                    allow_undated=bool(source.get('allowUndated'))))
            else:
                summaries.append(run_probe(config, site_slug, stream_key))
            if plan:
                summaries[-1].update({"baselineItems":int(plan["baseline_count"]),"additionalItems":max(0,int(summaries[-1].get("items",0))-int(plan["baseline_count"])),"targetItems":site_limit})
        except Exception as error:
            summaries.append({"site": site_slug, "status": "failed", "error": str(error)})
        finally:
            with lock_connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (f"scanner:international:{site_slug}",))
            lock_connection.close()
    return {
        "mode": mode,
        "streamKey": stream_key,
        "cutoff": cutoff.isoformat(),
        "limitPerSite": limit,
        "minimumPriceKrw": policy.minimum_price_krw,
        "exchangeRateDate": policy.exchange_rate_date,
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
    parser.add_argument("--extend-by", type=int, default=0, help="기존 체크포인트를 보존하고 사이트별 신규 매물을 추가 수집")
    parser.add_argument("--expansion-key", help="추가 수집 실행 식별자. 재시작 시 반드시 같은 값 사용")
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
        extend_by=max(0, args.extend_by), expansion_key=args.expansion_key,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if all(site.get("status") != "failed" for site in summary["sites"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
