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


def build_request_fingerprint(
    method: str,
    url: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    body: Optional[Mapping[str, Any]] = None,
) -> str:
    canonical = {
        "method": str(method or "GET").upper(),
        "url": str(url),
        "params": sorted((str(key), str(value)) for key, value in (params or {}).items()),
        "body": body or None,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def plan_initial_backfill(site_slug: str, page: int = 1) -> PlannedRequest:
    """Create a deterministic newest-first request plan without sending a request."""
    if page < 1:
        raise ValueError("page must be at least 1")
    source = source_by_slug(site_slug)
    params = {"page": page, "order": "posted_desc"}
    fingerprint = build_request_fingerprint("GET", source["listingUrl"], params=params)
    return PlannedRequest(
        site_slug=site_slug,
        method="GET",
        url=source["listingUrl"],
        params=params,
        body=None,
        cursor=f"page:{page}",
        request_fingerprint=fingerprint,
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
                    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (site_slug, stream_key),
                    KEY idx_source_sync_status (status, updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
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


def queue_planned_request(config: MySQLConfig, request: PlannedRequest) -> None:
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
                ) VALUES (%s, 'all', 'backward', 'planned', %s)
                ON DUPLICATE KEY UPDATE
                    next_cursor=IF(status='complete', next_cursor, VALUES(next_cursor)),
                    status=IF(status='complete', status, 'planned')
                """,
                (request.site_slug, request.cursor),
            )
    enqueue_crawl_task(
        config,
        site_slug=request.site_slug,
        origin=source_by_slug(request.site_slug)["baseUrl"],
        task_type="international_list",
        url=display_url,
        page=int(request.cursor.split(":", 1)[1]),
        priority=20,
        metadata={
            "method": request.method,
            "params": request.params,
            "body": request.body,
            "cursor": request.cursor,
            "request_fingerprint": request.request_fingerprint,
            "order": "posted_desc",
            "network_enabled": False,
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
                    last_success_cursor, last_request_fingerprint
                ) VALUES (%s, 'all', 'backward', %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    direction='backward', status=VALUES(status), next_cursor=VALUES(next_cursor),
                    last_success_cursor=VALUES(last_success_cursor),
                    last_request_fingerprint=VALUES(last_request_fingerprint), last_error=NULL
                """,
                (
                    request.site_slug,
                    "planned" if next_cursor else "complete",
                    next_cursor,
                    request.cursor,
                    request.request_fingerprint,
                ),
            )
            conn.commit()
            return True
