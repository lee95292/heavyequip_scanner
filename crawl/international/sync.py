from __future__ import annotations

import hashlib
import json
import urllib.parse
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from crawl.common import MySQLConfig, enqueue_crawl_task, ensure_crawl_queue, mysql_connect
from crawl.international.catalog import source_by_slug


@dataclass(frozen=True)
class PlannedRequest:
    site_slug: str
    method: str
    url: str
    params: dict[str, Any]
    body: Optional[dict[str, Any]]
    cursor: str
    request_fingerprint: str
    stream_key: str = "backfill"


def build_request_fingerprint(
    method: str,
    url: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    body: Optional[Mapping[str, Any]] = None,
    namespace: str = "",
) -> str:
    canonical = {
        "method": str(method or "GET").upper(),
        "url": str(url),
        "params": sorted((str(key), str(value)) for key, value in (params or {}).items()),
        "body": body or None,
        "namespace": namespace,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def plan_initial_backfill(site_slug: str, page: int = 1, *, stream_key: str = "backfill") -> PlannedRequest:
    """Create a deterministic newest-first request plan without sending a request."""
    if page < 1:
        raise ValueError("page must be at least 1")
    source = source_by_slug(site_slug)
    params = {"page": page, "order": "posted_desc"}
    fingerprint = build_request_fingerprint(
        "GET", source["listingUrl"], params=params, namespace=stream_key
    )
    return PlannedRequest(
        site_slug=site_slug,
        method="GET",
        url=source["listingUrl"],
        params=params,
        body=None,
        cursor=f"page:{page}",
        request_fingerprint=fingerprint,
        stream_key=stream_key,
    )


def plan_request(
    site_slug: str,
    *,
    url: str,
    cursor: str,
    stream_key: str,
) -> PlannedRequest:
    return PlannedRequest(
        site_slug=site_slug,
        method="GET",
        url=url,
        params={},
        body=None,
        cursor=cursor,
        request_fingerprint=build_request_fingerprint("GET", url, namespace=stream_key),
        stream_key=stream_key,
    )


def ensure_international_sync_tables(config: MySQLConfig) -> None:
    ensure_crawl_queue(config)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS source_sync_state (
                    site_slug VARCHAR(100) NOT NULL,
                    stream_key VARCHAR(191) NOT NULL DEFAULT 'all',
                    direction VARCHAR(20) NOT NULL DEFAULT 'backward',
                    status VARCHAR(20) NOT NULL DEFAULT 'idle',
                    next_cursor VARCHAR(500) NULL,
                    last_success_cursor VARCHAR(500) NULL,
                    newest_seen_at DATETIME NULL,
                    oldest_seen_at DATETIME NULL,
                    last_request_fingerprint CHAR(64) NULL,
                    last_error TEXT NULL,
                    item_count INT NOT NULL DEFAULT 0,
                    request_count INT NOT NULL DEFAULT 0,
                    stop_reason VARCHAR(100) NULL,
                    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (site_slug, stream_key),
                    KEY idx_source_sync_status (status, updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='source_sync_state'
                """,
                (config.database,),
            )
            existing = {row["COLUMN_NAME"] for row in cursor.fetchall()}
            additions = {
                "item_count": "INT NOT NULL DEFAULT 0",
                "request_count": "INT NOT NULL DEFAULT 0",
                "stop_reason": "VARCHAR(100) NULL",
            }
            for name, definition in additions.items():
                if name not in existing:
                    cursor.execute(f"ALTER TABLE source_sync_state ADD COLUMN {name} {definition}")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS source_request_log (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    site_slug VARCHAR(100) NOT NULL,
                    request_fingerprint CHAR(64) NOT NULL,
                    method VARCHAR(10) NOT NULL,
                    url TEXT NOT NULL,
                    cursor_value VARCHAR(500) NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'planned',
                    response_status INT NULL,
                    item_count INT NULL,
                    requested_at DATETIME NULL,
                    completed_at DATETIME NULL,
                    last_error TEXT NULL,
                    created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_source_request_fingerprint (site_slug, request_fingerprint),
                    KEY idx_source_request_resume (site_slug, status, id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS source_sync_item (
                    site_slug VARCHAR(100) NOT NULL,
                    stream_key VARCHAR(191) NOT NULL,
                    content_hash CHAR(64) NOT NULL,
                    created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (site_slug, stream_key, content_hash)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )


def queue_planned_request(config: MySQLConfig, request: PlannedRequest, *, enqueue: bool = True) -> None:
    """Persist a request plan idempotently. This function performs no network I/O."""
    ensure_international_sync_tables(config)
    query = urllib.parse.urlencode(request.params)
    display_url = f"{request.url}?{query}" if query else request.url
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO source_request_log (
                    site_slug, request_fingerprint, method, url, cursor_value, status
                ) VALUES (%s, %s, %s, %s, %s, 'planned')
                ON DUPLICATE KEY UPDATE id=id
                """,
                (
                    request.site_slug,
                    request.request_fingerprint,
                    request.method,
                    display_url,
                    request.cursor,
                ),
            )
            cursor.execute(
                """
                INSERT INTO source_sync_state (
                    site_slug, stream_key, direction, status, next_cursor
                ) VALUES (%s, %s, 'backward', 'planned', %s)
                ON DUPLICATE KEY UPDATE
                    next_cursor=IF(status='complete', next_cursor, VALUES(next_cursor)),
                    status=IF(status='complete', status, 'planned')
                """,
                (request.site_slug, request.stream_key, request.cursor),
            )
    if not enqueue:
        return
    enqueue_crawl_task(
        config,
        site_slug=request.site_slug,
        origin=source_by_slug(request.site_slug)["baseUrl"],
        task_type="international_list",
        url=display_url,
        page=int(request.cursor.rsplit(":", 1)[1]),
        priority=20,
        metadata={
            "method": request.method,
            "params": request.params,
            "body": request.body,
            "cursor": request.cursor,
            "request_fingerprint": request.request_fingerprint,
            "order": "posted_desc",
            "network_enabled": True,
            "stream_key": request.stream_key,
        },
        ensure=True,
    )


def claim_request(config: MySQLConfig, site_slug: str, request_fingerprint: str) -> bool:
    """Atomically claim a planned request; completed fingerprints can never be reclaimed."""
    ensure_international_sync_tables(config)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE source_request_log
                SET status='running', requested_at=CURRENT_TIMESTAMP, last_error=NULL
                WHERE site_slug=%s
                  AND request_fingerprint=%s
                  AND status IN ('planned', 'failed')
                """,
                (site_slug, request_fingerprint),
            )
            return int(cursor.rowcount or 0) == 1


def complete_request(
    config: MySQLConfig,
    request: PlannedRequest,
    *,
    response_status: int,
    item_count: int,
    next_cursor: Optional[str],
    newest_seen_at: Any = None,
    oldest_seen_at: Any = None,
    stop_reason: Optional[str] = None,
) -> bool:
    """Commit request completion and the next backward cursor after data persistence."""
    with mysql_connect(config, config.database) as conn:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE source_request_log
                SET status='complete', response_status=%s, item_count=%s,
                    completed_at=CURRENT_TIMESTAMP, last_error=NULL
                WHERE site_slug=%s AND request_fingerprint=%s AND status='running'
                """,
                (response_status, item_count, request.site_slug, request.request_fingerprint),
            )
            if int(cursor.rowcount or 0) != 1:
                conn.rollback()
                return False
            cursor.execute(
                """
                INSERT INTO source_sync_state (
                    site_slug, stream_key, direction, status, next_cursor,
                    last_success_cursor, last_request_fingerprint, newest_seen_at,
                    oldest_seen_at, item_count, request_count, stop_reason
                ) VALUES (%s, %s, 'backward', %s, %s, %s, %s, %s, %s, %s, 1, %s)
                ON DUPLICATE KEY UPDATE
                    direction='backward', status=VALUES(status), next_cursor=VALUES(next_cursor),
                    last_success_cursor=VALUES(last_success_cursor),
                    last_request_fingerprint=VALUES(last_request_fingerprint),
                    newest_seen_at=CASE
                        WHEN newest_seen_at IS NULL THEN VALUES(newest_seen_at)
                        WHEN VALUES(newest_seen_at) IS NULL THEN newest_seen_at
                        ELSE GREATEST(newest_seen_at, VALUES(newest_seen_at)) END,
                    oldest_seen_at=CASE
                        WHEN oldest_seen_at IS NULL THEN VALUES(oldest_seen_at)
                        WHEN VALUES(oldest_seen_at) IS NULL THEN oldest_seen_at
                        ELSE LEAST(oldest_seen_at, VALUES(oldest_seen_at)) END,
                    item_count=item_count + VALUES(item_count),
                    request_count=request_count + 1,
                    stop_reason=VALUES(stop_reason), last_error=NULL
                """,
                (
                    request.site_slug,
                    request.stream_key,
                    "planned" if next_cursor else "complete",
                    next_cursor,
                    request.cursor,
                    request.request_fingerprint,
                    newest_seen_at,
                    oldest_seen_at,
                    item_count,
                    stop_reason,
                ),
            )
            conn.commit()
            return True


def fail_request(config: MySQLConfig, request: PlannedRequest, error: Exception) -> None:
    message = str(error)[:4000]
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE source_request_log
                SET status='failed', last_error=%s
                WHERE site_slug=%s AND request_fingerprint=%s AND status='running'
                """,
                (message, request.site_slug, request.request_fingerprint),
            )
            cursor.execute(
                """
                INSERT INTO source_sync_state (site_slug, stream_key, direction, status, next_cursor, last_error)
                VALUES (%s, %s, 'backward', 'failed', %s, %s)
                ON DUPLICATE KEY UPDATE status='failed', next_cursor=VALUES(next_cursor), last_error=VALUES(last_error)
                """,
                (request.site_slug, request.stream_key, request.cursor, message),
            )


def recover_stale_requests(config: MySQLConfig, minutes: int = 30) -> int:
    ensure_international_sync_tables(config)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE source_request_log
                SET status='failed', last_error='stale running request recovered after process restart'
                WHERE status='running' AND requested_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s MINUTE)
                """,
                (max(1, int(minutes)),),
            )
            return int(cursor.rowcount or 0)


def sync_progress(config: MySQLConfig, site_slug: str, stream_key: str) -> dict[str, Any]:
    ensure_international_sync_tables(config)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, next_cursor, item_count, request_count, stop_reason, last_error
                FROM source_sync_state WHERE site_slug=%s AND stream_key=%s
                """,
                (site_slug, stream_key),
            )
            return cursor.fetchone() or {}


def finalize_stream(config: MySQLConfig, site_slug: str, stream_key: str, stop_reason: str) -> None:
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE source_sync_state
                SET status='complete', next_cursor=NULL, stop_reason=%s, last_error=NULL
                WHERE site_slug=%s AND stream_key=%s
                """,
                (stop_reason, site_slug, stream_key),
            )


def filter_new_stream_records(
    config: MySQLConfig,
    site_slug: str,
    stream_key: str,
    records: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if not records or limit <= 0:
        return []
    hashes = [str(record.get("content_hash") or "") for record in records]
    placeholders = ",".join(["%s"] * len(hashes))
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT content_hash FROM source_sync_item
                WHERE site_slug=%s AND stream_key=%s AND content_hash IN ({placeholders})
                """,
                (site_slug, stream_key, *hashes),
            )
            known = {row["content_hash"] for row in cursor.fetchall()}
    result: list[dict[str, Any]] = []
    seen = set(known)
    for record in records:
        content_hash = str(record.get("content_hash") or "")
        if content_hash and content_hash not in seen:
            result.append(record)
            seen.add(content_hash)
            if len(result) >= limit:
                break
    return result


def record_stream_items(
    config: MySQLConfig, site_slug: str, stream_key: str, records: list[dict[str, Any]]
) -> None:
    if not records:
        return
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT IGNORE INTO source_sync_item (site_slug, stream_key, content_hash)
                VALUES (%s, %s, %s)
                """,
                [(site_slug, stream_key, record["content_hash"]) for record in records],
            )
