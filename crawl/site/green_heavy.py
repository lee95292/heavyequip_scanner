from __future__ import annotations

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
    date_string,
    datetime_string,
    now_kst,
    parse_site_date,
    retry_once,
    upsert_records,
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
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        if config.proxy:
            self.session.proxies.update({"http": config.proxy, "https": config.proxy})

    def list_url(self, category_code: str, page: int = 1) -> str:
        query = {
            "cate_code": category_code,
            "mkco": "",
            "syear": "",
            "eyear": "",
            "find": "",
            "find1": "",
            "find2": "",
            "find3": "",
            "find4": "",
            "search": "",
            "limit": "70",
            "page": str(page),
        }
        return f"{BASE_URL}{LIST_PATH}?{urllib.parse.urlencode(query)}"

    def get_soup(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=25)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        if self.is_cupid_challenge(response.text):
            self.solve_cupid_challenge(response.text, response.url)
            retry_url = self.cupid_retry_url(response.text, response.url)
            response = self.session.get(retry_url, timeout=25)
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
            detail_url = urllib.parse.urljoin(BASE_URL, detail_anchor["href"])
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

    def parse_detail(self, detail_url: str) -> dict:
        soup = self.get_soup(detail_url)
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

    def crawl(self) -> list[dict]:
        cutoff = self.config.cutoff_datetime()
        crawled_at = datetime_string(now_kst())
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
        records: list[dict] = []

        for category in categories:
            print(f"[green_heavy] category {category.code} {category.name}")
            page = 1
            empty_period_pages = 0
            while True:
                crawl_url = self.list_url(category.code, page)
                soup = retry_once(
                    f"list cate={category.code} page={page}",
                    lambda: self.get_soup(crawl_url),
                    sleep_seconds=self.config.sleep_seconds,
                )
                if soup is None:
                    self.error_count += 1
                    break
                candidates = self.parse_listing_page(soup, crawl_url, category)
                print(f"[green_heavy] page={page} candidates={len(candidates)}")
                kept_on_page = 0
                page_records: list[dict] = []
                stop_all = False
                for record in candidates:
                    if self.config.max_items and (len(records) + len(page_records)) >= self.config.max_items:
                        stop_all = True
                        break
                    time.sleep(self.config.sleep_seconds)
                    detail = retry_once(
                        f"detail pid={record.get('pid')}",
                        lambda record=record: self.parse_detail(record["detail_url"]),
                        sleep_seconds=self.config.sleep_seconds,
                    )
                    if detail is None:
                        self.error_count += 1
                        continue
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
                        record["listing_name"] = clean_text(
                            f"{record.get('manufacturer') or ''} {detail['detail_title']}"
                        )
                    if detail.get("posted_at"):
                        record["posted_at"] = detail["posted_at"]
                    if detail.get("posted_date"):
                        record["posted_date"] = detail["posted_date"]
                    record["raw"]["detail"] = detail.get("raw_detail", {})
                    record["crawled_at"] = crawled_at
                    record["content_hash"] = build_content_hash(record)
                    if self.should_keep(record, cutoff):
                        page_records.append(record)
                        kept_on_page += 1
                        total_kept = len(records) + len(page_records)
                        if total_kept % 10 == 0:
                            print(f"[green_heavy] kept={total_kept}")

                self.persist_chunk(page_records, category, page)
                records.extend(page_records)

                if cutoff is not None:
                    if page_records:
                        empty_period_pages = 0
                    else:
                        empty_period_pages += 1
                        print(
                            f"[green_heavy] page={page} no period match "
                            f"streak={empty_period_pages}/{EMPTY_PERIOD_PAGE_GRACE + 1}"
                        )

                if stop_all or (self.config.max_items and len(records) >= self.config.max_items):
                    return records
                if self.config.max_pages and page >= self.config.max_pages:
                    break
                if cutoff is not None and empty_period_pages > EMPTY_PERIOD_PAGE_GRACE:
                    print(
                        f"[green_heavy] category {category.code} stop: "
                        f"no period match for {empty_period_pages} pages"
                    )
                    break
                next_page = page + 1
                if not self.has_next_page(soup, next_page):
                    print(f"[green_heavy] category {category.code} done at page={page}")
                    break
                page = next_page
                time.sleep(self.config.sleep_seconds)
        print(f"[green_heavy] crawl done records={len(records)}")
        return records


def run(config: CrawlConfig) -> dict:
    crawler = GreenHeavyCrawler(config)
    records = crawler.crawl()
    output_path = write_records(config.output_dir, SITE_SLUG, records)
    return {
        "site": SITE_SLUG,
        "origin": ORIGIN,
        "mode": config.normalized_mode(),
        "records": len(records),
        "inserted_or_updated": crawler.persisted_count,
        "chunks": len(crawler.chunk_paths),
        "errors": crawler.error_count,
        "output_path": str(output_path),
        "chunk_paths": crawler.chunk_paths[-5:],
        "database": config.mysql.database if config.write_db else None,
    }
