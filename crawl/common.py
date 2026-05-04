from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import pymysql


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "crawl" / "data"
DEFAULT_OUTPUT_DIR = DATA_DIR / "parsed"
DEFAULT_LOG_DIR = DATA_DIR / "logs"
DEFAULT_CONFIG_PATH = ROOT / "crawl" / "config.json"
MODEL_CSV_PATH = ROOT / "docs" / "const" / "model.csv"
KST = dt.timezone(dt.timedelta(hours=9))


MODE_ALIASES = {
    "all": "all",
    "전체": "all",
    "full": "all",
    "1d": "1d",
    "1day": "1d",
    "latest1day": "1d",
    "recent1day": "1d",
    "최근1일": "1d",
    "최1일": "1d",
    "1일": "1d",
    "5d": "5d",
    "5day": "5d",
    "5days": "5d",
    "latest5days": "5d",
    "recent5days": "5d",
    "최근5일": "5d",
    "5일": "5d",
    "1m": "1m",
    "1month": "1m",
    "month": "1m",
    "30d": "1m",
    "1달": "1m",
    "한달": "1m",
    "최근1달": "1m",
}


@dataclass
class MySQLConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "heavyequip_scanner"
    charset: str = "utf8mb4"
    connect_timeout: int = 10


@dataclass
class CrawlConfig:
    mode: str = "all"
    sleep_seconds: float = 0.3
    origins: tuple[str, ...] = ()
    proxy: Optional[str] = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    mysql: MySQLConfig = field(default_factory=MySQLConfig)
    max_pages: Optional[int] = None
    max_categories: Optional[int] = None
    max_items: Optional[int] = None
    write_db: bool = True

    def normalized_mode(self) -> str:
        return normalize_mode(self.mode)

    def cutoff_datetime(self) -> Optional[dt.datetime]:
        mode = self.normalized_mode()
        now = now_kst()
        if mode == "1d":
            return now - dt.timedelta(days=1)
        if mode == "5d":
            return now - dt.timedelta(days=5)
        if mode == "1m":
            return now - dt.timedelta(days=30)
        return None


def now_kst() -> dt.datetime:
    return dt.datetime.now(KST).replace(microsecond=0)


def normalize_mode(mode: str) -> str:
    key = str(mode or "all").strip().lower()
    return MODE_ALIASES.get(key, key)


def clean_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()
    return text


def redact_sensitive(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^:/\\s]+):([^@/\\s]+)@", r"\1***:***@", text)


def load_mysql_config(path: Path = DEFAULT_CONFIG_PATH) -> MySQLConfig:
    if not path.exists():
        return MySQLConfig()
    data = json.loads(path.read_text(encoding="utf-8"))
    mysql_data = data.get("mysql", data)
    return MySQLConfig(
        host=str(mysql_data.get("host", "127.0.0.1")),
        port=int(mysql_data.get("port", 3306)),
        user=str(mysql_data.get("user", "root")),
        password=str(mysql_data.get("password", "")),
        database=str(mysql_data.get("database", "heavyequip_scanner")),
        charset=str(mysql_data.get("charset", "utf8mb4")),
        connect_timeout=int(mysql_data.get("connect_timeout", 10)),
    )


def parse_site_date(value: str, now: Optional[dt.datetime] = None) -> Optional[dt.datetime]:
    text = clean_text(value)
    if not text:
        return None
    now = now or now_kst()
    try:
        parsed_iso = dt.datetime.fromisoformat(text)
        if parsed_iso.tzinfo is None:
            parsed_iso = parsed_iso.replace(tzinfo=KST)
        return parsed_iso.astimezone(KST)
    except ValueError:
        pass
    patterns = [
        ("%Y-%m-%d %H:%M:%S", text),
        ("%Y-%m-%d %H:%M", text),
        ("%Y-%m-%d", text),
        ("%Y.%m.%d %H:%M:%S", text),
        ("%Y.%m.%d", text),
    ]
    for fmt, candidate in patterns:
        try:
            parsed = dt.datetime.strptime(candidate, fmt)
            return parsed.replace(tzinfo=KST)
        except ValueError:
            pass
    short = re.fullmatch(r"(\d{2})[./-](\d{1,2})[./-](\d{1,2})", text)
    if short:
        year = 2000 + int(short.group(1))
        return dt.datetime(year, int(short.group(2)), int(short.group(3)), tzinfo=KST)
    month_day = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})", text)
    if month_day:
        return dt.datetime(now.year, int(month_day.group(1)), int(month_day.group(2)), tzinfo=KST)
    return None


def date_string(value: Optional[dt.datetime]) -> Optional[str]:
    return value.date().isoformat() if value else None


def datetime_string(value: Optional[dt.datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def mysql_datetime(value: Any) -> Optional[str]:
    parsed = parse_site_date(str(value or ""))
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else None


def mysql_date(value: Any) -> Optional[str]:
    parsed = parse_site_date(str(value or ""))
    return parsed.strftime("%Y-%m-%d") if parsed else None


def parse_price_krw(value: Any) -> Optional[int]:
    text = clean_text(value)
    if not text or any(token in text for token in ("협의", "문의", "상담")):
        return None
    number_match = re.search(r"([\d,]+(?:\.\d+)?)", text)
    if not number_match:
        return None
    amount = float(number_match.group(1).replace(",", ""))
    if "억" in text:
        return int(amount * 100_000_000)
    if "만원" in text:
        return int(amount * 10_000)
    if "천원" in text:
        return int(amount * 1_000)
    if "원" in text:
        return int(amount)
    return int(amount)


def normalize_model_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Z가-힣]", "", clean_text(value).upper())


def load_model_norm_map(path: Path = MODEL_CSV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return {}
    import csv
    import io

    rows = list(csv.reader(io.StringIO(text)))
    values = rows[0] if rows else []
    result: dict[str, str] = {}
    for value in values:
        model = clean_text(value)
        key = normalize_model_key(model)
        if key:
            result[key] = model
    return result


MODEL_NORM_MAP = load_model_norm_map()


def model_norm(value: Any) -> Optional[str]:
    key = normalize_model_key(value)
    if not key:
        return None
    if key in MODEL_NORM_MAP:
        return MODEL_NORM_MAP[key]
    # Many listing titles append work tools or condition text to a valid model code.
    # Prefer the longest known model code contained in the site model string.
    for known_key, canonical in sorted(MODEL_NORM_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if len(known_key) >= 4 and known_key in key:
            return canonical
    return None


def build_content_hash(record: dict[str, Any]) -> str:
    fields = [
        "origin",
        "detail_url",
        "posted_at",
        "posted_date",
        "listing_name",
        "model_name",
        "price",
        "contact",
    ]
    payload = {key: record.get(key) or "" for key in fields}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mysql_connect(config: MySQLConfig, database: Optional[str] = None):
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=database,
        charset=config.charset,
        connect_timeout=config.connect_timeout,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def url_hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def mysql_identifier(value: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z_]+", value):
        raise ValueError(f"MySQL identifier contains unsupported characters: {value!r}")
    return f"`{value}`"


def ensure_database(config: MySQLConfig) -> None:
    database_name = mysql_identifier(config.database)
    print(f"[db] ensure {config.database}.listings")
    with mysql_connect(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {database_name} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS listings (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    content_hash CHAR(64) NULL,
                    origin VARCHAR(255) NULL,
                    source_site VARCHAR(100) NULL,
                    crawl_url TEXT NULL,
                    detail_url TEXT NULL,
                    pid VARCHAR(64) NULL,
                    category_code VARCHAR(32) NULL,
                    category_name VARCHAR(255) NULL,
                    listing_name VARCHAR(500) NULL,
                    model_name VARCHAR(255) NULL,
                    model_norm VARCHAR(255) NULL,
                    description MEDIUMTEXT NULL,
                    price VARCHAR(100) NULL,
                    price_krw BIGINT NULL,
                    contact VARCHAR(255) NULL,
                    posted_date DATE NULL,
                    posted_at DATETIME NULL,
                    crawled_at DATETIME NULL,
                    manufacturer VARCHAR(255) NULL,
                    manufactured_ym VARCHAR(50) NULL,
                    location VARCHAR(255) NULL,
                    seller VARCHAR(255) NULL,
                    status VARCHAR(100) NULL,
                    view_count INT NULL,
                    raw_json JSON NULL,
                    payload_json JSON NULL,
                    created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_listings_content_hash (content_hash),
                    KEY idx_listings_origin (origin),
                    KEY idx_listings_posted_date (posted_date),
                    KEY idx_listings_posted_at (posted_at),
                    KEY idx_listings_crawled_at (crawled_at),
                    KEY idx_listings_price_krw (price_krw),
                    KEY idx_listings_model_norm (model_norm)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )


def ensure_crawl_queue(config: MySQLConfig) -> None:
    ensure_database(config)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_tasks (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    site_slug VARCHAR(100) NOT NULL,
                    origin VARCHAR(255) NULL,
                    task_type VARCHAR(50) NOT NULL,
                    url_hash CHAR(64) NOT NULL,
                    url TEXT NOT NULL,
                    category_code VARCHAR(32) NULL,
                    category_name VARCHAR(255) NULL,
                    page INT NULL,
                    priority INT NOT NULL DEFAULT 100,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    attempts INT NOT NULL DEFAULT 0,
                    last_status_code INT NULL,
                    last_error TEXT NULL,
                    next_run_at DATETIME NULL,
                    success_at DATETIME NULL,
                    metadata_json JSON NULL,
                    created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_crawl_tasks_site_url (site_slug, url_hash),
                    KEY idx_crawl_tasks_pick (site_slug, status, next_run_at, priority, id),
                    KEY idx_crawl_tasks_type (site_slug, task_type),
                    KEY idx_crawl_tasks_category (site_slug, category_code, page)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )


def enqueue_crawl_task(
    config: MySQLConfig,
    *,
    site_slug: str,
    origin: str,
    task_type: str,
    url: str,
    category_code: Optional[str] = None,
    category_name: Optional[str] = None,
    page: Optional[int] = None,
    priority: int = 100,
    metadata: Optional[dict[str, Any]] = None,
    reset_done: bool = False,
    ensure: bool = True,
) -> None:
    if ensure:
        ensure_crawl_queue(config)
    status_sql = "IF(status = 'running', 'running', 'pending')" if reset_done else (
        "IF(status = 'done', 'done', IF(status = 'running', 'running', 'pending'))"
    )
    success_sql = "IF(status = 'running', success_at, NULL)" if reset_done else "success_at"
    attempts_sql = "IF(status = 'running', attempts, 0)" if reset_done else "attempts"
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO crawl_tasks (
                    site_slug, origin, task_type, url_hash, url, category_code, category_name,
                    page, priority, status, attempts, metadata_json
                ) VALUES (
                    %(site_slug)s, %(origin)s, %(task_type)s, %(url_hash)s, %(url)s,
                    %(category_code)s, %(category_name)s, %(page)s, %(priority)s,
                    'pending', 0, %(metadata_json)s
                )
                ON DUPLICATE KEY UPDATE
                    origin=VALUES(origin),
                    task_type=VALUES(task_type),
                    url=VALUES(url),
                    category_code=VALUES(category_code),
                    category_name=VALUES(category_name),
                    page=VALUES(page),
                    priority=VALUES(priority),
                    metadata_json=VALUES(metadata_json),
                    status={status_sql},
                    attempts={attempts_sql},
                    last_status_code=NULL,
                    last_error=NULL,
                    next_run_at=NULL,
                    success_at={success_sql},
                    updated_at=CURRENT_TIMESTAMP
                """,
                {
                    "site_slug": site_slug,
                    "origin": origin,
                    "task_type": task_type,
                    "url_hash": url_hash(url),
                    "url": url,
                    "category_code": category_code,
                    "category_name": category_name,
                    "page": page,
                    "priority": priority,
                    "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                },
            )


def fetch_pending_crawl_tasks(
    config: MySQLConfig,
    site_slug: str,
    limit: int = 20,
    ensure: bool = True,
) -> list[dict[str, Any]]:
    if ensure:
        ensure_crawl_queue(config)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM crawl_tasks
                WHERE site_slug = %s
                  AND status = 'pending'
                  AND (next_run_at IS NULL OR next_run_at <= CURRENT_TIMESTAMP)
                ORDER BY priority ASC, id ASC
                LIMIT %s
                """,
                (site_slug, limit),
            )
            return list(cursor.fetchall())


def mark_crawl_task_started(config: MySQLConfig, task_id: int) -> None:
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE crawl_tasks SET status='running', updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                (task_id,),
            )


def reset_running_crawl_tasks(
    config: MySQLConfig,
    site_slug: str,
    older_than_seconds: Optional[int] = None,
) -> int:
    where = "site_slug=%s AND status='running'"
    params: list[Any] = [site_slug]
    if older_than_seconds is not None:
        where += " AND updated_at <= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s SECOND)"
        params.append(older_than_seconds)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE crawl_tasks
                SET status='pending',
                    next_run_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE {where}
                """,
                params,
            )
            return int(cursor.rowcount or 0)


def mark_crawl_task_done(config: MySQLConfig, task_id: int) -> None:
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE crawl_tasks
                SET status='done',
                    last_status_code=NULL,
                    last_error=NULL,
                    next_run_at=NULL,
                    success_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (task_id,),
            )


def mark_crawl_task_retry(
    config: MySQLConfig,
    task_id: int,
    *,
    status_code: Optional[int],
    error: str,
    retry_after_seconds: int,
) -> None:
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE crawl_tasks
                SET status='pending',
                    attempts=attempts + 1,
                    last_status_code=%s,
                    last_error=%s,
                    next_run_at=DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s SECOND),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (status_code, error[:2000], retry_after_seconds, task_id),
            )


def crawl_task_counts(config: MySQLConfig, site_slug: str) -> dict[str, int]:
    ensure_crawl_queue(config)
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM crawl_tasks
                WHERE site_slug = %s
                GROUP BY status
                """,
                (site_slug,),
            )
            return {row["status"]: int(row["cnt"]) for row in cursor.fetchall()}


def nullable_int(value: Any) -> Optional[int]:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d+", text.replace(",", ""))
    return int(match.group(0)) if match else None


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    record.setdefault("model_norm", model_norm(record.get("model_name")))
    if not record.get("model_norm"):
        record["model_norm"] = model_norm(record.get("listing_name"))
    record.setdefault("price_krw", parse_price_krw(record.get("price")))
    return record


def upsert_records(config: MySQLConfig, records: Iterable[dict[str, Any]]) -> int:
    records = list(records)
    if not records:
        print("[db] upsert skip: 0 records")
        return 0
    ensure_database(config)
    print(f"[db] upsert start: {len(records)} records")
    with mysql_connect(config, config.database) as conn:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO listings (
                    content_hash, origin, source_site, crawl_url, detail_url, pid,
                    category_code, category_name, listing_name, model_name, model_norm,
                    description, price, price_krw, contact, posted_date, posted_at,
                    crawled_at, manufacturer, manufactured_ym, location, seller, status,
                    view_count, raw_json, payload_json
                ) VALUES (
                    %(content_hash)s, %(origin)s, %(source_site)s, %(crawl_url)s,
                    %(detail_url)s, %(pid)s, %(category_code)s, %(category_name)s,
                    %(listing_name)s, %(model_name)s, %(model_norm)s, %(description)s,
                    %(price)s, %(price_krw)s, %(contact)s, %(posted_date)s,
                    %(posted_at)s, %(crawled_at)s, %(manufacturer)s, %(manufactured_ym)s,
                    %(location)s, %(seller)s, %(status)s, %(view_count)s,
                    %(raw_json)s, %(payload_json)s
                )
                ON DUPLICATE KEY UPDATE
                    origin=VALUES(origin),
                    source_site=VALUES(source_site),
                    crawl_url=VALUES(crawl_url),
                    detail_url=VALUES(detail_url),
                    pid=VALUES(pid),
                    category_code=VALUES(category_code),
                    category_name=VALUES(category_name),
                    listing_name=VALUES(listing_name),
                    model_name=VALUES(model_name),
                    model_norm=VALUES(model_norm),
                    description=VALUES(description),
                    price=VALUES(price),
                    price_krw=VALUES(price_krw),
                    contact=VALUES(contact),
                    posted_date=VALUES(posted_date),
                    posted_at=VALUES(posted_at),
                    crawled_at=VALUES(crawled_at),
                    manufacturer=VALUES(manufacturer),
                    manufactured_ym=VALUES(manufactured_ym),
                    location=VALUES(location),
                    seller=VALUES(seller),
                    status=VALUES(status),
                    view_count=VALUES(view_count),
                    raw_json=VALUES(raw_json),
                    payload_json=VALUES(payload_json),
                    updated_at=CURRENT_TIMESTAMP
            """
            for record in records:
                enriched = enrich_record(record)
                payload = {
                    "content_hash": enriched.get("content_hash"),
                    "origin": enriched.get("origin"),
                    "source_site": enriched.get("source_site"),
                    "crawl_url": enriched.get("crawl_url"),
                    "detail_url": enriched.get("detail_url"),
                    "pid": enriched.get("pid"),
                    "category_code": enriched.get("category_code"),
                    "category_name": enriched.get("category_name"),
                    "listing_name": enriched.get("listing_name"),
                    "model_name": enriched.get("model_name"),
                    "model_norm": enriched.get("model_norm"),
                    "description": enriched.get("description"),
                    "price": enriched.get("price"),
                    "price_krw": enriched.get("price_krw"),
                    "contact": enriched.get("contact"),
                    "posted_date": mysql_date(enriched.get("posted_date") or enriched.get("posted_at")),
                    "posted_at": mysql_datetime(enriched.get("posted_at")),
                    "crawled_at": mysql_datetime(enriched.get("crawled_at")),
                    "manufacturer": enriched.get("manufacturer"),
                    "manufactured_ym": enriched.get("manufactured_ym"),
                    "location": enriched.get("location"),
                    "seller": enriched.get("seller"),
                    "status": enriched.get("status"),
                    "view_count": nullable_int(enriched.get("view_count")),
                    "raw_json": json.dumps(enriched.get("raw"), ensure_ascii=False, sort_keys=True),
                    "payload_json": json.dumps(enriched, ensure_ascii=False, sort_keys=True),
                }
                cursor.execute(sql, payload)
    print(f"[db] upsert done: {len(records)} records")
    return len(records)


def write_records(output_dir: Path, site_slug: str, records: list[dict[str, Any]]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = [enrich_record(record) for record in records]
    stamp = now_kst().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{site_slug}_{stamp}.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[file] wrote {len(records)} records -> {path}")
    return path


def write_record_chunk(
    output_dir: Path,
    site_slug: str,
    chunk_name: str,
    records: list[dict[str, Any]],
) -> Path:
    chunk_dir = output_dir / site_slug / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    records = [enrich_record(record) for record in records]
    safe_chunk_name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", chunk_name).strip("_")
    stamp = now_kst().strftime("%Y%m%d_%H%M%S")
    path = chunk_dir / f"{stamp}_{safe_chunk_name}.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[file] chunk wrote {len(records)} records -> {path}")
    return path


def error_request_context(error: Exception) -> dict[str, Any]:
    context: dict[str, Any] = {}
    request = getattr(error, "request", None)
    response = getattr(error, "response", None)
    if request is not None:
        context["method"] = getattr(request, "method", None)
        context["url"] = redact_sensitive(getattr(request, "url", None))
    if response is not None:
        context["status_code"] = getattr(response, "status_code", None)
        context["response_url"] = redact_sensitive(getattr(response, "url", None))
        reason = getattr(response, "reason", None)
        if reason:
            context["reason"] = clean_text(reason)
    return {key: value for key, value in context.items() if value not in (None, "")}


def write_skip_log(label: str, error: Exception, attempts: int) -> Path:
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_kst()
    path = DEFAULT_LOG_DIR / f"skip_{stamp.strftime('%Y%m%d')}.jsonl"
    entry = {
        "ts": datetime_string(stamp),
        "label": label,
        "attempts": attempts,
        "error_type": type(error).__name__,
        "error": redact_sensitive(error),
        "request": error_request_context(error),
        "traceback": redact_sensitive("".join(traceback.format_exception_only(type(error), error)).strip()),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def retry_once(label: str, func, sleep_seconds: float = 0.3):
    last_error = None
    attempts = 2
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as error:  # noqa: BLE001 - crawler should continue after transient site failures.
            last_error = error
            print(f"[retry] {label} failed attempt={attempt}: {type(error).__name__}: {error}")
            if attempt < attempts and sleep_seconds > 0:
                time.sleep(sleep_seconds)
    log_path = write_skip_log(label, last_error, attempts) if last_error else None
    log_suffix = f" log={log_path}" if log_path else ""
    print(f"[skip] {label}: {type(last_error).__name__}: {last_error}{log_suffix}")
    return None
