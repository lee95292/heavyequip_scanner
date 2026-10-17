from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import requests

from crawl.common import KST, clean_text


USER_AGENT = "Mozilla/5.0 (compatible; HeavyEquipScanner/1.0; +https://scan.mglee.dev)"
_HTTP_PROXY = ""
_SESSION = requests.Session()


def configure_proxy(proxy_url: str) -> None:
    global _HTTP_PROXY
    value = str(proxy_url or "").strip()
    if not value.startswith(("http://", "https://")):
        raise ValueError("international.http_proxy must be an http(s) URL")
    _HTTP_PROXY = value
    _SESSION.proxies.update({"http": value, "https": value})


class SourceAccessError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    payloads: list[dict[str, Any]]
    has_next: bool


def fetch_text(url: str, *, timeout: int = 35) -> tuple[int, str, str]:
    if not _HTTP_PROXY:
        raise SourceAccessError("international HTTP proxy is required; direct requests are disabled")
    headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.8",
        }
    try:
        response = _SESSION.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        status = int(response.status_code)
        final_url = response.url
        body = response.text
    except requests.RequestException as error:
        raise SourceAccessError(f"network error: {type(error).__name__}") from error
    if status != 200:
        raise SourceAccessError(f"HTTP {status}: {final_url}", status=status)
    return status, final_url, body


class _MachinerylineParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.div_depth = 0
        self.current: dict[str, Any] | None = None
        self.current_depth = -1
        self.capture: str | None = None
        self.capture_tag: str | None = None
        self.text: list[str] = []
        self.payloads: list[dict[str, Any]] = []
        self.has_next = False

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return set((attrs.get("class") or "").split())

    def handle_starttag(self, tag: str, raw_attrs: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in raw_attrs}
        classes = self._classes(attrs)
        if tag == "div":
            self.div_depth += 1
        if tag == "div" and "sales-list-item" in classes and attrs.get("data-code"):
            self.current = {
                "id": attrs["data-code"],
                "title": attrs.get("data-name"),
                "manufacturer": attrs.get("data-brand"),
            }
            self.current_depth = self.div_depth
        if self.current is not None:
            if tag == "a" and "sales-item-title-link" in classes:
                self.current["url"] = attrs.get("href")
                self.capture = "title"
            elif "price-value" in classes:
                self.capture = "displayPrice"
            elif "cat-name" in classes:
                self.capture = "category"
            elif "location-text" in classes:
                self.capture = "location"
            elif "sl-main-props__item" in classes:
                title = (attrs.get("title") or "").lower()
                self.capture = "year" if title == "year" else ("hours" if "hour" in title else None)
            if self.capture:
                self.capture_tag = tag
                self.text = []
        if tag == "a" and (clean_text(attrs.get("rel")).lower() == "next" or "pgn-next" in classes):
            self.has_next = True

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.capture and tag == self.capture_tag:
            value = clean_text(" ".join(self.text))
            if value and self.current is not None:
                self.current[self.capture] = value
            self.capture = None
            self.capture_tag = None
            self.text = []
        if tag == "div" and self.current is not None and self.div_depth == self.current_depth:
            code = str(self.current.get("id") or "")
            if re.fullmatch(r"\d{20}", code):
                try:
                    stamp = dt.datetime.strptime(code[:12], "%y%m%d%H%M%S").replace(tzinfo=KST)
                    self.current["createdAt"] = stamp.isoformat()
                except ValueError:
                    pass
            self.payloads.append(self.current)
            self.current = None
        if tag == "div":
            self.div_depth -= 1


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_next_data = False
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and values.get("id") == "__NEXT_DATA__":
            self.in_next_data = True

    def handle_data(self, data: str) -> None:
        if self.in_next_data:
            self.chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_next_data:
            self.in_next_data = False


def machineryline_url(page: int, minimum_price_eur: int | None = None) -> str:
    params: dict[str, Any] = {"page": page}
    if minimum_price_eur is not None:
        # Verified against Machineryline's public search form: pr0 is minimum
        # price and scurr selects the currency used by that filter.
        params.update({"pr0": max(1, int(minimum_price_eur)), "scurr": "EUR"})
    query = urllib.parse.urlencode(params)
    return f"https://machineryline.com/-/construction-equipment--c85?{query}"


def fetch_machineryline(page: int, minimum_price_eur: int | None = None) -> FetchResult:
    url = machineryline_url(page, minimum_price_eur)
    status, final_url, body = fetch_text(url)
    parser = _MachinerylineParser()
    parser.feed(body)
    if not parser.payloads:
        raise SourceAccessError("Machineryline listing markup contained no items", status=status)
    # The page contains promoted listings followed by the actual newest-first list.
    # Identity-based upserts make repeated promotions harmless.
    return FetchResult(final_url, status, parser.payloads, parser.has_next)


def inspect_ironplanet() -> dict:
    """Inspect public embedded JSON without fabricating listing dates."""
    status, url, body = fetch_text("https://www.ironplanet.com/marketplace-mpe-construction")
    decoder = json.JSONDecoder()
    items = []
    for match in re.finditer(r"quickviews\.push\(\s*", body):
        try:
            item, _ = decoder.raw_decode(body[match.end():])
            if isinstance(item, dict):
                items.append(item)
        except ValueError:
            continue
    dated = sum(bool(item.get("postedAt") or item.get("createdAt") or item.get("datePublished")) for item in items)
    return {"httpStatus":status,"url":url,"items":len(items),"itemsWithRegistrationDate":dated,
            "responseFormat":"HTML containing quickviews.push(JSON)",
            "status":"needs_registration_date" if items and dated != len(items) else "needs_parser_validation",
            "reason":"Public listing JSON is accessible, but registration-date sorting and the recent-year cutoff are not verified. No listing dates are fabricated and no items are imported by this probe."}


IRONPLANET_PRICE_FILTERS = ('inventory',)


def ironplanet_url(price_filter: str, page: int) -> str:
    if price_filter not in IRONPLANET_PRICE_FILTERS:
        raise ValueError('unsupported IronPlanet price currency')
    if page == 1:
        return 'https://www.ironplanet.com/marketplace-mpe-construction'
    return 'https://www.ironplanet.com/jsp/s/search.ips?' + urllib.parse.urlencode({
        'ct': 1, 'ms': 'M', 'sm': 0,
        'pstart': (max(1, page)-1)*60, 'prows': 60,
    })


def parse_ironplanet_page(body: str, url: str, status: int = 200) -> FetchResult:
    decoder = json.JSONDecoder()
    items = []
    for match in re.finditer(r'quickviews\.push\(\s*', body):
        try:
            item, _ = decoder.raw_decode(body[match.end():])
            if isinstance(item, dict) and item.get('equipId'):
                items.append({**item, 'crawlUrl': url})
        except ValueError as error:
            raise SourceAccessError('IronPlanet quickview JSON changed', status=status) from error
    offset = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('pstart',['0'])[0])
    next_offsets = [int(value) for value in re.findall(r'[?&]pstart=(\d+)', body)]
    if not items and not re.search(r'0 items|no (?:items|results)|no equipment', body, re.I):
        raise SourceAccessError('IronPlanet listing JSON missing; not treated as end of results', status=status)
    return FetchResult(url, status, items, any(value > offset for value in next_offsets))


def fetch_ironplanet(price_filter: str, page: int) -> FetchResult:
    status, final_url, body = fetch_text(ironplanet_url(price_filter, page))
    return parse_ironplanet_page(body, final_url, status)


MASCUS_CATEGORY_CATALOGS = {
    # Machine-only construction categories. Parts, tyres, scaffolding,
    # compressors, generators, marine and generic "other" categories are
    # intentionally excluded.
    "excavators": "construction",
    "telehandlers": "construction",
    "backhoeloaders": "construction",
    "cranesmain": "construction",
    "platformsandcranes": "construction",
    "dumpersmain": "construction",
    "roadconstruction": "construction",
    "loaders": "construction",
    "undergroundminingequipment": "construction",
    "drillingrigs": "construction",
    "dozers": "construction",
    "constructiontrenchers": "construction",
    "constructionhoistsandworkplatforms": "construction",
    "concreteequipment": "construction",
    "rollers": "construction",
    "drillingequipmentmain": "construction",
    "asphaltmachinesmain": "construction",
    "compactionequipmentmain": "construction",
    "pilingequipmentmain": "construction",
    "asphaltrecyclers": "construction",
    # Mascus publishes forklifts under its material-handling catalog.
    "forklifttrucks": "materialhandling",
}
MASCUS_CATEGORIES = tuple(MASCUS_CATEGORY_CATALOGS)


def mascus_url(category: str, page: int, minimum_price_usd: int | None = None) -> str:
    try:
        catalog = MASCUS_CATEGORY_CATALOGS[category]
    except KeyError as error:
        raise ValueError(f"unsupported Mascus category: {category}") from error
    filters = f"catalogs={catalog}&categories={category}"
    if minimum_price_usd is not None:
        # Verified in the public UI. A positive minimum also excludes
        # "On Request" listings at the source before parsing.
        filters += f"&price.min={max(1, int(minimum_price_usd))}"
    return f"https://www.mascus.com/+/{filters}/{max(1, int(page))},createdate_desc,search.html"


def fetch_mascus(category: str, page: int, minimum_price_usd: int | None = None) -> FetchResult:
    if category not in MASCUS_CATEGORIES:
        raise ValueError(f"unsupported Mascus category: {category}")
    url = mascus_url(category, page, minimum_price_usd)
    status, final_url, body = fetch_text(url)
    parser = _NextDataParser()
    parser.feed(body)
    if not parser.chunks:
        raise SourceAccessError("Mascus __NEXT_DATA__ payload missing", status=status)
    try:
        data = json.loads("".join(parser.chunks))
        search = data["props"]["pageProps"]["searchRes"]["searchData"]
        items = search["items"]
        total = int(search.get("totalResults") or 0)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SourceAccessError("Mascus search payload shape changed", status=status) from error
    for item in items:
        item["crawlUrl"] = final_url
    return FetchResult(final_url, status, items, page * 40 < total)
