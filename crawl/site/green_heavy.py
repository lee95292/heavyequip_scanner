from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from crawl.common import (
    CrawlConfig,
    build_content_hash,
    clean_text,
    crawl_task_counts,
    date_string,
    datetime_string,
    enqueue_crawl_task,
    ensure_crawl_queue,
    fetch_pending_crawl_tasks,
    mark_crawl_task_done,
    mark_crawl_task_retry,
    mark_crawl_task_started,
    now_kst,
    parse_site_date,
    reset_running_crawl_tasks,
    retry_once,
    upsert_records,
    write_skip_log,
    write_record_chunk,
    write_records,
)


SITE_SLUG = "green_heavy"
SOURCE_SITE = "그린중기"
ORIGIN = "https://4396200.com"
BASE_URL = "https://www.4396200.com"
LIST_PATH = "/sub8_1_s.html"
DETAIL_PATH = "/sub8_1_vvv.html"
DEFAULT_CATEGORY = "100100"
EMPTY_PERIOD_PAGE_GRACE = 2
QUEUE_BATCH_SIZE = 1
QUEUE_RATE_LIMIT_COOLDOWN_SECONDS = 15 * 60

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class Category:
    code: str
    name: str


class GreenHeavyCrawler:
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.chunk_paths: list[str] = []
        self.persisted_count = 0
        self.error_count = 0
        self.session = self.build_session()

    def build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(REQUEST_HEADERS)
        if self.config.proxy:
            session.proxies.update({"http": self.config.proxy, "https": self.config.proxy})
        return session

    def reset_session(self) -> None:
        self.session.close()
        self.session = self.build_session()

    def list_url(self, category_code: str, page: int = 1) -> str:
        query = {
            "cate_code": category_code,
            "limit": "70",
            "page": str(page),
        }
        return f"{BASE_URL}{LIST_PATH}?{urllib.parse.urlencode(query)}"

    def compact_detail_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(urllib.parse.urljoin(BASE_URL, url))
        query = urllib.parse.parse_qs(parsed.query)
        pid = (query.get("pid") or [""])[0]
        if pid:
            return f"{BASE_URL}{DETAIL_PATH}?{urllib.parse.urlencode({'pid': pid})}"
        return urllib.parse.urlunparse(parsed)

    def get_soup(self, url: str, referer: Optional[str] = None) -> BeautifulSoup:
        headers = {"Referer": referer} if referer else None
        response = self.session.get(url, timeout=25, headers=headers)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        if self.is_cupid_challenge(response.text):
            self.solve_cupid_challenge(response.text, response.url)
            retry_url = self.cupid_retry_url(response.text, response.url)
            response = self.session.get(retry_url, timeout=25, headers=headers)
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            if self.is_cupid_challenge(response.text):
                raise RuntimeError("Green Heavy CUPID challenge was not cleared")
        return BeautifulSoup(response.text, "html.parser")

    def is_cupid_challenge(self, html: str) -> bool:
        return "CUPID" in html and "slowAES.decrypt" in html and "/cupid.js" in html

    def solve_cupid_challenge(self, html: str, response_url: str) -> None:
        match = re.search(
            r'var\s+a=toNumbers\("([0-9a-fA-F]+)"\)\s*,\s*'
            r'b=toNumbers\("([0-9a-fA-F]+)"\)\s*,\s*'
            r'c=toNumbers\("([0-9a-fA-F]+)"\)',
            html,
        )
        if not match:
            raise RuntimeError("Green Heavy CUPID challenge parameters were not found")
        key, iv, ciphertext = (bytes.fromhex(value) for value in match.groups())
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        cupid = (decryptor.update(ciphertext) + decryptor.finalize()).hex()
        host = urllib.parse.urlparse(response_url).hostname or "www.4396200.com"
        self.session.cookies.set("CUPID", cupid, domain=host, path="/")
        print("[green_heavy] CUPID challenge solved")

    def cupid_retry_url(self, html: str, response_url: str) -> str:
        match = re.search(r'location\.href\s*=\s*"([^"]+)"', html)
        if match:
            return urllib.parse.urljoin(response_url, match.group(1))
        parsed = urllib.parse.urlparse(response_url)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        attempt = int((query.get("ckattempt") or ["0"])[0] or "0") + 1
        query["ckattempt"] = [str(attempt)]
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))

    def discover_categories(self) -> list[Category]:
        soup = self.get_soup(self.list_url(DEFAULT_CATEGORY))
        categories: list[Category] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "sub8_1_s.html?cate_code=" not in href:
                continue
            parsed = urllib.parse.urlparse(urllib.parse.urljoin(BASE_URL, href))
            query = urllib.parse.parse_qs(parsed.query)
            code = (query.get("cate_code") or [""])[0]
            if not re.fullmatch(r"\d{6}", code) or code in seen:
                continue
            name = clean_text(anchor.get_text(" ", strip=True)) or code
            seen.add(code)
            categories.append(Category(code=code, name=name))
        if categories:
            return categories
        if self.listing_table(soup):
            return [Category(code=DEFAULT_CATEGORY, name="굴삭기 1.3 ㎥ 이상")]
        raise RuntimeError("Green Heavy category discovery failed: no category links or listing table found")

    def listing_table(self, soup: BeautifulSoup):
        for table in soup.find_all("table"):
            headers = [clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
            if "모델명" in headers and "등록날짜" in headers:
                return table
        return None

    def is_pinned_row(self, row, cells: list) -> bool:
        first = cells[0] if cells else None
        if first:
            marker = " ".join(
                [
                    *(img.get("src", "") for img in first.find_all("img")),
                    *(img.get("alt", "") for img in first.find_all("img")),
                    first.get_text(" ", strip=True),
                ]
            ).lower()
            if "btn16.png" in marker or "vip" in marker:
                return True
            if "btn17.png" in marker or "cool" in marker:
                return True
        texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        return len(texts) > 9 and texts[9] == "그린중기"

    def parse_listing_page(self, soup: BeautifulSoup, crawl_url: str, category: Category) -> list[dict]:
        table = self.listing_table(soup)
        if table is None:
            return []
        rows = []
        for row in table.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 12:
                continue
            if self.is_pinned_row(row, cells):
                continue
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            detail_anchor = row.find("a", href=re.compile(r"sub8_1_vvv\.html\?pid="))
            if not detail_anchor:
                continue
            site_detail_url = urllib.parse.urljoin(BASE_URL, detail_anchor["href"])
            detail_url = self.compact_detail_url(site_detail_url)
            pid_match = re.search(r"[?&]pid=(\d+)", detail_url)
            pid = pid_match.group(1) if pid_match else None
            posted_dt = parse_site_date(values[10])
            manufacturer = values[3]
            model_name = values[4]
            listing_name = clean_text(f"{manufacturer} {model_name}")
            rows.append(
                {
                    "origin": ORIGIN,
                    "source_site": SOURCE_SITE,
                    "crawl_url": crawl_url,
                    "detail_url": detail_url,
                    "pid": pid,
                    "posted_date": date_string(posted_dt),
                    "listing_name": listing_name,
                    "model_name": model_name,
                    "description": None,
                    "price": values[8],
                    "contact": None,
                    "posted_at": datetime_string(posted_dt),
                    "category_code": category.code,
                    "category_name": category.name,
                    "manufacturer": manufacturer,
                    "manufactured_ym": values[5],
                    "location": values[7],
                    "seller": values[9],
                    "status": values[6],
                    "view_count": values[11],
                    "raw": {
                        "trade_type": values[2],
                        "list_values": values,
                        "site_detail_url": site_detail_url,
                    },
                }
            )
        return rows

    def parse_key_value_tables(self, soup: BeautifulSoup) -> dict[str, str]:
        data: dict[str, str] = {}
        for row in soup.find_all("tr"):
            children = row.find_all(["th", "td"], recursive=False)
            index = 0
            while index < len(children) - 1:
                label_node = children[index]
                value_node = children[index + 1]
                if label_node.name == "th" and value_node.name == "td":
                    label = clean_text(label_node.get_text(" ", strip=True))
                    value = clean_text(value_node.get_text(" ", strip=True))
                    if label and value:
                        data[label] = value
                    index += 2
                else:
                    index += 1
        return data

    def parse_detail(self, detail_url: str, referer: Optional[str] = None) -> dict:
        soup = self.get_soup(self.compact_detail_url(detail_url), referer=referer)
        kv = self.parse_key_value_tables(soup)
        comment = soup.select_one(".product_comment")
        description = clean_text(comment.get_text("\n", strip=True)) if comment else None
        posted_at = None
        for node in soup.select("td.ar"):
            parsed = parse_site_date(node.get_text(" ", strip=True))
            if parsed:
                posted_at = parsed
                break
        title = None
        title_node = soup.select_one("table.shop_table td.al strong")
        if title_node:
            title = clean_text(title_node.get_text(" ", strip=True))
        return {
            "detail_title": title,
            "posted_at": datetime_string(posted_at),
            "posted_date": date_string(posted_at),
            "model_name": kv.get("모델명"),
            "price": kv.get("가격"),
            "contact": kv.get("연락처"),
            "manufacturer": kv.get("제작사"),
            "location": kv.get("위치"),
            "status": kv.get("상태"),
            "manufactured_ym": kv.get("제작년월"),
            "description": description,
            "raw_detail": kv,
        }

    def has_next_page(self, soup: BeautifulSoup, next_page: int) -> bool:
        pattern = re.compile(rf"[?&]page={next_page}(?:&|#|$)")
        return any(pattern.search(anchor.get("href", "")) for anchor in soup.find_all("a", href=True))

    def should_keep(self, record: dict, cutoff) -> bool:
        if cutoff is None:
            return True
        posted_at = parse_site_date(record.get("posted_at") or record.get("posted_date") or "")
        return bool(posted_at and posted_at >= cutoff)

    def persist_chunk(self, records: list[dict], category: Category, page: int) -> None:
        if not records:
            return
        chunk_name = f"cate_{category.code}_page_{page}"
        path = write_record_chunk(self.config.output_dir, SITE_SLUG, chunk_name, records)
        self.chunk_paths.append(str(path))
        if not self.config.write_db:
            return
        inserted = retry_once(
            f"db upsert {chunk_name}",
            lambda: upsert_records(self.config.mysql, records),
            sleep_seconds=self.config.sleep_seconds,
        )
        if inserted is None:
            self.error_count += 1
            return
        self.persisted_count += inserted

    def persist_record_batch(self, records: list[dict], chunk_name: str) -> None:
        if not records:
            return
        path = write_record_chunk(self.config.output_dir, SITE_SLUG, chunk_name, records)
        self.chunk_paths.append(str(path))
        if not self.config.write_db:
            return
        inserted = retry_once(
            f"db upsert {chunk_name}",
            lambda: upsert_records(self.config.mysql, records),
            sleep_seconds=self.config.sleep_seconds,
        )
        if inserted is None:
            self.error_count += 1
            return
        self.persisted_count += inserted

    def task_metadata(self, task: dict) -> dict:
        raw = task.get("metadata_json") or "{}"
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def category_from_task(self, task: dict, metadata: dict) -> Category:
        return Category(
            code=str(task.get("category_code") or metadata.get("category_code") or ""),
            name=str(task.get("category_name") or metadata.get("category_name") or ""),
        )

    def status_code_from_error(self, error: Exception) -> Optional[int]:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        return int(status_code) if status_code is not None else None

    def queue_list_task(self, category: Category, page: int = 1, empty_period_pages: int = 0) -> None:
        enqueue_crawl_task(
            self.config.mysql,
            site_slug=SITE_SLUG,
            origin=ORIGIN,
            task_type="list",
            url=self.list_url(category.code, page),
            category_code=category.code,
            category_name=category.name,
            page=page,
            priority=10,
            metadata={
                "category_code": category.code,
                "category_name": category.name,
                "page": page,
                "empty_period_pages": empty_period_pages,
            },
            reset_done=True,
            ensure=False,
        )

    def queue_detail_tasks(self, records: list[dict], category: Category, page: int) -> int:
        queued = 0
        for record in records:
            enqueue_crawl_task(
                self.config.mysql,
                site_slug=SITE_SLUG,
                origin=ORIGIN,
                task_type="detail",
                url=record["detail_url"],
                category_code=category.code,
                category_name=category.name,
                page=page,
                priority=5,
                metadata={
                    "category_code": category.code,
                    "category_name": category.name,
                    "page": page,
                    "referer": record.get("crawl_url"),
                    "record": record,
                },
                reset_done=True,
                ensure=False,
            )
            queued += 1
        return queued

    def mark_task_error(self, task: dict, error: Exception) -> bool:
        status_code = self.status_code_from_error(error)
        error_text = f"{type(error).__name__}: {error}"
        retry_after = QUEUE_RATE_LIMIT_COOLDOWN_SECONDS if status_code == 400 else max(60, int(self.config.sleep_seconds * 20))
        mark_crawl_task_retry(
            self.config.mysql,
            int(task["id"]),
            status_code=status_code,
            error=error_text,
            retry_after_seconds=retry_after,
        )
        log_path = write_skip_log(
            f"queue {SITE_SLUG} {task['task_type']} id={task['id']}",
            error,
            int(task.get("attempts") or 0) + 1,
        )
        print(
            f"[green_heavy] task retry id={task['id']} type={task['task_type']} "
            f"status={status_code} after={retry_after}s log={log_path}"
        )
        if status_code == 400:
            self.reset_session()
            print("[green_heavy] 400 response detected; pausing this run to avoid rate-limit bursts")
            return True
        return False

    def process_list_task(self, task: dict, cutoff) -> tuple[list[dict], bool]:
        metadata = self.task_metadata(task)
        category = self.category_from_task(task, metadata)
        page = int(task.get("page") or metadata.get("page") or 1)
        try:
            soup = self.get_soup(task["url"])
        except Exception as error:  # noqa: BLE001 - task queue keeps retry state.
            self.error_count += 1
            return [], self.mark_task_error(task, error)

        candidates = self.parse_listing_page(soup, task["url"], category)
        if cutoff is None:
            in_period_candidates = candidates
        else:
            in_period_candidates = [record for record in candidates if self.should_keep(record, cutoff)]
        queued_details = self.queue_detail_tasks(in_period_candidates, category, page)
        mark_crawl_task_done(self.config.mysql, int(task["id"]))
        print(
            f"[green_heavy] list done cate={category.code} page={page} "
            f"candidates={len(candidates)} detail_tasks={queued_details}"
        )

        empty_period_pages = int(metadata.get("empty_period_pages") or 0)
        if cutoff is not None:
            empty_period_pages = 0 if in_period_candidates else empty_period_pages + 1
            if empty_period_pages > EMPTY_PERIOD_PAGE_GRACE:
                print(
                    f"[green_heavy] category {category.code} stop queue: "
                    f"no period match for {empty_period_pages} pages"
                )
                return [], False

        next_page = page + 1
        if self.config.max_pages and page >= self.config.max_pages:
            return [], False
        if self.has_next_page(soup, next_page):
            self.queue_list_task(category, next_page, empty_period_pages)
            print(f"[green_heavy] queued next cate={category.code} page={next_page}")
        else:
            print(f"[green_heavy] category {category.code} done at page={page}")
        return [], False

    def process_detail_task(self, task: dict, crawled_at: str, cutoff) -> tuple[list[dict], bool]:
        metadata = self.task_metadata(task)
        record = metadata.get("record")
        if not isinstance(record, dict):
            mark_crawl_task_done(self.config.mysql, int(task["id"]))
            print(f"[green_heavy] detail task missing record metadata id={task['id']}")
            return [], False

        try:
            detail_url = self.compact_detail_url(task["url"])
            referer = metadata.get("referer") or record.get("crawl_url")
            record["detail_url"] = detail_url
            detail = self.parse_detail(detail_url, referer=referer)
        except Exception as error:  # noqa: BLE001 - task queue keeps retry state.
            self.error_count += 1
            return [], self.mark_task_error(task, error)

        for key in (
            "model_name",
            "price",
            "contact",
            "manufacturer",
            "location",
            "status",
            "manufactured_ym",
            "description",
        ):
            if detail.get(key):
                record[key] = detail[key]
        if detail.get("detail_title"):
            record["listing_name"] = clean_text(f"{record.get('manufacturer') or ''} {detail['detail_title']}")
        if detail.get("posted_at"):
            record["posted_at"] = detail["posted_at"]
        if detail.get("posted_date"):
            record["posted_date"] = detail["posted_date"]
        record.setdefault("raw", {})
        record["raw"]["detail"] = detail.get("raw_detail", {})
        record["crawled_at"] = crawled_at
        record["content_hash"] = build_content_hash(record)
        mark_crawl_task_done(self.config.mysql, int(task["id"]))
        if not self.should_keep(record, cutoff):
            return [], False
        return [record], False

    def crawl(self) -> list[dict]:
        cutoff = self.config.cutoff_datetime()
        crawled_at = datetime_string(now_kst())
        ensure_crawl_queue(self.config.mysql)
        reset_count = reset_running_crawl_tasks(self.config.mysql, SITE_SLUG)
        if reset_count:
            print(f"[green_heavy] reset running tasks={reset_count}")
        categories = (
            retry_once(
                "green_heavy discover_categories",
                self.discover_categories,
                sleep_seconds=self.config.sleep_seconds,
            )
            or []
        )
        if self.config.max_categories:
            categories = categories[: self.config.max_categories]
        print(f"[green_heavy] categories={len(categories)} mode={self.config.normalized_mode()}")
        for category in categories:
            self.queue_list_task(category, 1, 0)
        print(f"[green_heavy] queue={crawl_task_counts(self.config.mysql, SITE_SLUG)}")

        records: list[dict] = []
        batch_records: list[dict] = []
        paused = False
        for category in categories:
            print(f"[green_heavy] queued category {category.code} {category.name}")

        while True:
            if self.config.max_items and len(records) >= self.config.max_items:
                break
            tasks = fetch_pending_crawl_tasks(self.config.mysql, SITE_SLUG, QUEUE_BATCH_SIZE, ensure=False)
            if not tasks:
                break
            for task in tasks:
                if self.config.max_items and len(records) >= self.config.max_items:
                    break
                mark_crawl_task_started(self.config.mysql, int(task["id"]))
                time.sleep(self.config.sleep_seconds)
                if task["task_type"] == "list":
                    new_records, should_pause = self.process_list_task(task, cutoff)
                elif task["task_type"] == "detail":
                    new_records, should_pause = self.process_detail_task(task, crawled_at, cutoff)
                else:
                    mark_crawl_task_done(self.config.mysql, int(task["id"]))
                    print(f"[green_heavy] unknown task type={task['task_type']} id={task['id']}")
                    new_records, should_pause = [], False
                if new_records:
                    batch_records.extend(new_records)
                    records.extend(new_records)
                    if len(records) % 10 == 0:
                        print(f"[green_heavy] kept={len(records)}")
                if len(batch_records) >= 20:
                    self.persist_record_batch(batch_records, f"queue_batch_{len(self.chunk_paths) + 1}")
                    batch_records = []
                if should_pause:
                    paused = True
                    break
            if paused:
                break
        if batch_records:
            self.persist_record_batch(batch_records, f"queue_batch_{len(self.chunk_paths) + 1}")
        if paused:
            print(f"[green_heavy] crawl paused queue={crawl_task_counts(self.config.mysql, SITE_SLUG)}")
        print(f"[green_heavy] crawl done records={len(records)}")
        return records


def run(config: CrawlConfig) -> dict:
    crawler = GreenHeavyCrawler(config)
    records = crawler.crawl()
    output_path = write_records(config.output_dir, SITE_SLUG, records)
    queue_counts = crawl_task_counts(config.mysql, SITE_SLUG)
    return {
        "site": SITE_SLUG,
        "origin": ORIGIN,
        "mode": config.normalized_mode(),
        "records": len(records),
        "inserted_or_updated": crawler.persisted_count,
        "chunks": len(crawler.chunk_paths),
        "errors": crawler.error_count,
        "queue": queue_counts,
        "output_path": str(output_path),
        "chunk_paths": crawler.chunk_paths[-5:],
        "database": config.mysql.database if config.write_db else None,
    }
