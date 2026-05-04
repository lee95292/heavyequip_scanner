#!/usr/bin/env python3
import csv
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


warnings.filterwarnings("ignore", message="Unverified HTTPS request")

INPUT = Path("/Users/myeonggyu/Downloads/korea_heavy_equipment_keyword_homepage_expanded_v2_2026-04-19.csv")
OUT_DIR = Path("/Users/myeonggyu/github/aetc/heavyequip-scanner")
TODAY = dt.date.today().isoformat()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
}

LISTING_KEYWORDS = [
    "매물",
    "중고",
    "판매",
    "팝니다",
    "보유",
    "제품",
    "장비",
    "굴삭",
    "굴착",
    "지게차",
    "덤프",
    "로더",
    "크레인",
    "건설기계",
    "product",
    "products",
    "goods",
    "shop",
    "sale",
    "sell",
    "used",
    "machine",
    "equipment",
    "board",
    "bbs",
    "sub6",
    "sub8",
    "m02",
]

NEGATIVE_KEYWORDS = [
    "회사소개",
    "인사말",
    "오시는길",
    "공지",
    "공지사항",
    "고객센터",
    "자주하는질문",
    "묻고답하기",
    "질문",
    "자유게시판",
    "견적",
    "문의",
    "로그인",
    "회원",
    "채용",
    "개인정보",
    "약관",
    "intro",
    "company",
    "notice",
    "contact",
    "login",
    "join",
]

PRICE_RE = re.compile(r"(?:(?:[0-9]{2,}(?:,[0-9]{3})*)|(?:[0-9]+억\s*[0-9]*))\s*(?:만원|원)")
YEAR_RE = re.compile(r"(?:19|20)\d{2}\s*년")
COUNT_PATTERNS = [
    re.compile(r"총\s*게시물\s*([0-9,]{1,7})\s*건", re.I),
    re.compile(r"검색결과\s*[:：]?\s*([0-9,]{1,7})\s*건", re.I),
    re.compile(r"(?:매물|상품|제품)\s*(?:수|건수)?\s*[:：]?\s*([0-9,]{1,7})\s*(?:건|개|대)", re.I),
    re.compile(r"전체보기\s*\(([0-9,]{1,7})\)", re.I),
    re.compile(r"총\s*([0-9,]{1,7})\s*(?:건|개|대)\b", re.I),
    re.compile(r"전체\s*([0-9,]{1,7})\s*(?:건|개|대)\b", re.I),
]
API_HINT_RE = re.compile(
    r"(fetch\s*\(|axios\.|XMLHttpRequest|\$\.ajax|/api/|graphql|_next/data|rest_route|wp-json|ajax)",
    re.I,
)


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: str = ""
    final_url: str = ""
    content_type: str = ""
    text: str = ""
    error: str = ""


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    url = url.replace("；", ";")
    if url.startswith("www."):
        url = "https://" + url
    if not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    return url


def split_urls(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*;\s*|\s+,\s+", value.strip())
    urls = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        urls.append(normalize_url(part))
    return urls


def host_key(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return p.netloc.lower().replace("www.", "")


def canonical_url_key(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path or "/"
    return urllib.parse.urlunparse(("", netloc, path, "", parsed.query, ""))


def fetch(session: requests.Session, url: str, timeout: float = 14) -> FetchResult:
    try:
        r = session.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        if (r.status_code in (403, 406) or not (200 <= r.status_code < 400)) and url.startswith("https://"):
            alt = "http://" + url[len("https://") :]
            try:
                alt_r = session.get(alt, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
                if 200 <= alt_r.status_code < 400:
                    r = alt_r
            except Exception:
                pass
        text = r.text if "text" in r.headers.get("content-type", "") or r.text else ""
        return FetchResult(
            url=url,
            ok=200 <= r.status_code < 400,
            status=str(r.status_code),
            final_url=r.url,
            content_type=r.headers.get("content-type", ""),
            text=text,
        )
    except Exception as e:
        if url.startswith("https://"):
            alt = "http://" + url[len("https://") :]
            try:
                r = session.get(alt, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
                text = r.text if "text" in r.headers.get("content-type", "") or r.text else ""
                return FetchResult(
                    url=alt,
                    ok=200 <= r.status_code < 400,
                    status=str(r.status_code),
                    final_url=r.url,
                    content_type=r.headers.get("content-type", ""),
                    text=text,
                )
            except Exception:
                pass
        return FetchResult(url=url, ok=False, error=f"{type(e).__name__}: {e}")


def strip_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def link_candidates(base_url: str, html: str) -> list[tuple[int, str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if host_key(abs_url) != host_key(base_url):
            continue
        label = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        probe = (label + " " + href).lower()
        score = sum(4 for k in LISTING_KEYWORDS if k.lower() in probe)
        score -= sum(3 for k in NEGATIVE_KEYWORDS if k.lower() in probe)
        if "bbs/board.php" in href:
            score += 4
        if "bo_table" in href:
            score += 3
        if "wr_id" in href:
            score -= 8
        if not label:
            score -= 2
        if re.search(r"(page|list|product|goods|sell|sale|sub\d+|m\d+)", href, re.I):
            score += 2
        if score <= 0:
            continue
        key = urllib.parse.urldefrag(abs_url)[0]
        if key in seen:
            continue
        seen.add(key)
        out.append((score, key, label[:80]))
    return sorted(out, key=lambda x: x[0], reverse=True)


def extract_count(text: str) -> tuple[Optional[int], str]:
    for pat in COUNT_PATTERNS:
        candidates = []
        for m in pat.finditer(text or ""):
            raw = m.group(1).replace(",", "")
            try:
                num = int(raw)
            except ValueError:
                continue
            if 0 <= num <= 500000:
                candidates.append((num, m.group(0)[:60]))
        if candidates:
            return candidates[0]
    return None, ""


def extract_page_max(html: str, url: str) -> Optional[int]:
    soup = BeautifulSoup(html or "", "html.parser")
    nums = []
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href = urllib.parse.urljoin(url, a.get("href", ""))
        for raw in re.findall(r"(?:[?&](?:page|paged|p|pageNo|page_no|PB_\d+|board_page)=)(\d{1,5})", href, re.I):
            nums.append(int(raw))
    return max(nums) if nums else None


def estimate_item_count(html: str, text: str) -> tuple[int, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    url_hint = ""
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical and canonical.get("href"):
        url_hint = canonical["href"]
    host = host_key(url_hint) if url_hint else ""

    daara_rows = 0
    for tr in soup.find_all("tr"):
        row_text = re.sub(r"\s+", " ", tr.get_text(" ", strip=True))
        if row_text.startswith("제품리스트 ") and ("모델명:" in row_text or "가격" in row_text):
            daara_rows += 1
    if daara_rows:
        return daara_rows, f"다아라 제품리스트 행 수={daara_rows}"

    hrefs = []
    detail_ids = set()
    for a in soup.find_all("a", href=True):
        h = a.get("href", "")
        label = a.get_text(" ", strip=True)
        probe = h + " " + label
        if re.search(r"(pid=|sub8_1_vvv|wr_id=|idx=|/sell/\d+|view|product|goods|item|no=|seq=|mch-)", probe, re.I):
            if any(k in probe for k in ["만원", "굴삭", "지게", "덤프", "로더", "크레인", "현대", "두산", "볼보"]):
                clean = urllib.parse.urldefrag(h)[0]
                id_match = re.search(r"(?:pid|wr_id|idx|no|seq)=([0-9A-Za-z_-]+)", clean)
                detail_ids.add(id_match.group(0) if id_match else clean)
                hrefs.append(clean)
    unique_links = len(detail_ids or set(hrefs))
    price_hits = len(PRICE_RE.findall(text or ""))
    year_hits = len(YEAR_RE.findall(text or ""))
    if unique_links:
        return unique_links, f"노출 매물 상세링크 수={unique_links}, price_hits={price_hits}, year_hits={year_hits}"
    if price_hits:
        return price_hits, f"가격 패턴 수={price_hits}, year_hits={year_hits}"
    if year_hits:
        return year_hits, f"연식 패턴 수={year_hits}"
    else:
        return 0, "매물 패턴 미검출"


def response_kind(fr: FetchResult) -> tuple[str, str]:
    ct = (fr.content_type or "").lower()
    txt = fr.text or ""
    if "json" in ct:
        return "API(JSON 응답)", "Content-Type JSON"
    if fr.status == "403" and "cloudflare" in txt.lower():
        return "확인불가(Cloudflare 차단)", "Cloudflare challenge"
    if not fr.ok:
        return "확인불가(요청 실패)", fr.error or fr.status
    if API_HINT_RE.search(txt):
        if "__NEXT_DATA__" in txt or "_next/static" in txt:
            return "HTML+JS/내장데이터", "Next.js/스크립트 API 단서"
        return "HTML+API호출 단서", "fetch/ajax/api 문자열 탐지"
    return "HTML 응답", "초기 HTML 본문에서 확인"


def is_listing_like(text: str, html: str, url: str) -> bool:
    low = (text + " " + url).lower()
    kw = sum(1 for k in LISTING_KEYWORDS if k.lower() in low)
    has_item_signal = bool(PRICE_RE.search(text or "") or YEAR_RE.search(text or ""))
    return kw >= 2 or has_item_signal or "bo_table" in url or "bmode=view" in url


def analyze_page(fr: FetchResult) -> dict:
    text = strip_text(fr.text) if fr.text else ""
    title = page_title(fr.text)
    kind, basis = response_kind(fr)
    total_count, count_basis = extract_count(text)
    visible_count, visible_basis = estimate_item_count(fr.text, text)
    page_max = extract_page_max(fr.text, fr.final_url or fr.url)
    non_inventory = is_non_inventory_page(title, text, fr.final_url or fr.url)
    if total_count is not None:
        count = total_count
        method = f"페이지 표시 총건수: {count_basis}"
    elif page_max and page_max > 1 and visible_count:
        per_page = visible_count if visible_count <= 80 else 20
        count = page_max * per_page
        method = f"페이지네이션 추정: page_max={page_max}, first_page_visible={visible_count}"
    else:
        count = visible_count
        method = visible_basis
    listing_flag = is_listing_like(text, fr.text, fr.final_url or fr.url)
    if non_inventory:
        count = 0
        visible_count = 0
        listing_flag = False
        method = "비매물 게시판/지원 페이지로 판단"
    if kind == "HTML+API호출 단서" and (count or visible_count) and listing_flag:
        kind = "HTML 응답(스크립트 단서 있음)"
        basis = "초기 HTML에 매물/목록 포함 + ajax/api 문자열 존재"
    crawl_fields = []
    parsed = urllib.parse.urlparse(fr.final_url or fr.url)
    if parsed.query:
        crawl_fields.append("query_params=" + parsed.query[:120])
    for key in ["bo_table", "page", "cate_cd", "find", "search", "cid", "bmode", "idx", "wr_id"]:
        if key in urllib.parse.parse_qs(parsed.query):
            crawl_fields.append(key)
    if "Cloudflare" in kind:
        crawl_fields.append("브라우저/쿠키 필요")
    elif "API" in kind or "JS" in kind:
        crawl_fields.append("스크립트/API 엔드포인트 확인 필요")
    else:
        crawl_fields.append("requests+BeautifulSoup 가능")
    return {
        "response_kind": kind,
        "response_basis": basis,
        "listing_count": count,
        "count_method": method,
        "visible_item_count": visible_count,
        "page_max": page_max or "",
        "listing_like": listing_flag,
        "crawl_fields": " | ".join(dict.fromkeys(crawl_fields)),
        "page_title": title,
        "text_sample": text[:180],
    }


def page_title(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    if soup.title and soup.title.string:
        return re.sub(r"\s+", " ", soup.title.string.strip())[:120]
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"][:120]
    return ""


def is_non_inventory_page(title: str, text: str, url: str) -> bool:
    probe = f"{title} {text[:140]} {url}".lower()
    hard_negative = [
        "질문/자유게시판",
        "자유게시판",
        "묻고답하기",
        "자주하는질문",
        "고객센터",
        "공지사항",
        "구인구직",
    ]
    if any(term in probe for term in hard_negative):
        inventory_title_terms = ["덤프트럭", "굴삭기", "지게차", "로더", "크레인", "매물", "매매", "제품"]
        return not any(term in (title or "") for term in inventory_title_terms)
    return False


def choose_best(session: requests.Session, urls: list[str]) -> tuple[FetchResult, dict, list[str]]:
    attempted = []
    fetched: list[tuple[FetchResult, dict]] = []
    seen = set()
    queue = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            queue.append(u)
    # Fetch homepage/source URLs first and expand with high-scoring same-host links.
    for url in list(queue):
        fr = fetch(session, url)
        attempted.append(f"{url} [{fr.status or fr.error[:50]}]")
        if fr.text:
            for score, cand, label in link_candidates(fr.final_url or url, fr.text)[:7]:
                if cand not in seen:
                    seen.add(cand)
                    queue.append(cand)
        fetched.append((fr, analyze_page(fr)))
        time.sleep(0.08)
        if len(queue) > 12:
            queue = queue[:12]
    for url in queue[len(fetched):]:
        fr = fetch(session, url)
        attempted.append(f"{url} [{fr.status or fr.error[:50]}]")
        fetched.append((fr, analyze_page(fr)))
        time.sleep(0.08)
    if not fetched:
        dummy = FetchResult(url="", ok=False, error="no url")
        return dummy, analyze_page(dummy), attempted
    def score(item):
        fr, a = item
        s = 0
        if fr.ok:
            s += 10
        if a["listing_like"]:
            s += 25
        s += min(int(a["listing_count"] or 0), 200) / 10
        if "HTML 응답" in a["response_kind"]:
            s += 2
        if "Cloudflare" in a["response_kind"]:
            s -= 10
        low = (fr.final_url or fr.url).lower()
        s += sum(3 for k in LISTING_KEYWORDS if k.lower() in low)
        s -= sum(4 for k in NEGATIVE_KEYWORDS if k.lower() in low)
        return s
    best = max(fetched, key=score)
    return best[0], best[1], attempted


def row_urls(row: dict) -> list[str]:
    urls = []
    for col in ["홈페이지/상세URL", "출처URL"]:
        urls.extend(split_urls(row.get(col, "")))
    out = []
    seen = set()
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def source_rows() -> list[dict]:
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def external_rows() -> list[dict]:
    # Sites discovered by web search and then verified by the same analyzer.
    return [
        {
            "No": "WEB-1",
            "업체명": "퍼펙트82중장비",
            "홈페이지/상세URL": "https://www.perfect82.com/camain",
            "출처URL": "https://www.perfect82.com/camain",
            "출처유형": "웹검색 추가",
            "검토메모": "검색 결과: 굴삭기/덤프/지게차/화물차 직거래 매매 플랫폼",
        },
        {
            "No": "WEB-2",
            "업체명": "Backhoe.kr 사용장비 거래",
            "홈페이지/상세URL": "https://www.backhoe.kr/",
            "출처URL": "https://www.backhoe.kr/",
            "출처유형": "웹검색 추가",
            "검토메모": "검색 결과: 굴삭기 산업 포털, 사용장비 거래 메뉴",
        },
        {
            "No": "WEB-3",
            "업체명": "건설기계코리아(KU21)",
            "홈페이지/상세URL": "https://ku21.com/",
            "출처URL": "https://ku21.com/p/sell/171",
            "출처유형": "웹검색 추가",
            "검토메모": "검색 결과: 중고 중장비 매물 포털로 노출",
        },
        {
            "No": "WEB-4",
            "업체명": "공사마스터 중고장비매매",
            "홈페이지/상세URL": "https://www.04master.com/",
            "출처URL": "https://www.04master.com/",
            "출처유형": "웹검색 추가",
            "검토메모": "검색 결과: 중고장비매매 메뉴 노출",
        },
        {
            "No": "WEB-5",
            "업체명": "대한건설기계매매협회 매물정보",
            "홈페이지/상세URL": "https://www.daehanmachine.com/",
            "출처URL": "https://www.daehanmachine.com/",
            "출처유형": "웹검색 추가",
            "검토메모": "검색 결과: 중고건설기계 매물정보 대표 사이트로 언급",
        },
        {
            "No": "WEB-6",
            "업체명": "건설장비포탈 건설기계코리아",
            "홈페이지/상세URL": "http://ku21.com/",
            "출처URL": "http://ku21.com/p/sell/171",
            "출처유형": "웹검색 추가",
            "검토메모": "HTTPS DNS 실패 대비 HTTP 직접 확인용",
        },
    ]


def main() -> int:
    session = requests.Session()
    rows = source_rows() + external_rows()
    results = []
    for i, row in enumerate(rows, 1):
        urls = row_urls(row)
        fr, analysis, attempted = choose_best(session, urls)
        input_status = "원본CSV" if str(row.get("No", "")).isdigit() else "웹추가"
        home = row.get("홈페이지/상세URL", "")
        source = row.get("출처URL", "")
        best_url = fr.final_url or fr.url
        results.append(
            {
                "정렬순위": "",
                "원본구분": input_status,
                "원본No": row.get("No", ""),
                "업체명/사이트명": row.get("업체명", ""),
                "도메인": host_key(best_url) if best_url else "",
                "홈페이지URL": home,
                "원본출처URL": source,
                "확인한_매물페이지URL": best_url,
                "매물수_추정": analysis["listing_count"],
                "매물수_산정근거": analysis["count_method"],
                "응답방식": analysis["response_kind"],
                "응답방식_근거": analysis["response_basis"],
                "HTTP상태": fr.status,
                "Content-Type": fr.content_type,
                "페이지제목": analysis["page_title"],
                "매물페이지여부": "Y" if analysis["listing_like"] and analysis["listing_count"] else ("추정" if analysis["listing_like"] else "N"),
                "페이지네이션_최대": analysis["page_max"],
                "첫페이지_노출매물수": analysis["visible_item_count"],
                "크롤링_필요정보/전략": analysis["crawl_fields"],
                "요청시도URL": " || ".join(attempted[:16]),
                "원본_공식성등급": row.get("공식성등급", ""),
                "원본_사업품목": row.get("사업/취급품목", ""),
                "원본_대표전화": row.get("대표전화", ""),
                "원본_검토메모": row.get("검토메모", ""),
                "자동확인일": TODAY,
            }
        )
        print(f"{i:03d}/{len(rows)} {row.get('업체명','')} -> {analysis['listing_count']} {analysis['response_kind']} {best_url}", flush=True)

    def sort_key(r):
        try:
            cnt = int(r["매물수_추정"])
        except Exception:
            cnt = 0
        original_boost = 1 if r["원본구분"] == "원본CSV" else 0
        return (-cnt, r["매물페이지여부"] == "N", -original_boost, str(r["업체명/사이트명"]))

    results.sort(key=sort_key)
    for idx, r in enumerate(results, 1):
        r["정렬순위"] = idx

    csv_path = OUT_DIR / f"heavy_equipment_sites_inventory_sorted_{TODAY}.csv"
    summary_csv_path = OUT_DIR / f"heavy_equipment_unique_sites_sorted_{TODAY}.csv"
    xlsx_path = OUT_DIR / f"heavy_equipment_sites_inventory_sorted_{TODAY}.xlsx"
    json_path = OUT_DIR / f"heavy_equipment_sites_inventory_sorted_{TODAY}.json"

    df = pd.DataFrame(results)
    summary_rows = []
    df["_summary_url_key"] = df["확인한_매물페이지URL"].fillna("").map(canonical_url_key)
    for (domain, listing_url_key), group in df.groupby(["도메인", "_summary_url_key"], dropna=False, sort=False):
        group_sorted = group.sort_values(["매물수_추정", "정렬순위"], ascending=[False, True])
        first = group_sorted.iloc[0]
        representative_name = first["업체명/사이트명"] if len(group) == 1 else f"{domain} 공용매물/플랫폼"
        summary_rows.append(
            {
                "사이트순위": "",
                "도메인": domain,
                "대표사이트명": representative_name,
                "확인한_매물페이지URL": first["확인한_매물페이지URL"],
                "매물수_추정": first["매물수_추정"],
                "매물수_산정근거": first["매물수_산정근거"],
                "응답방식": first["응답방식"],
                "매물페이지여부": first["매물페이지여부"],
                "연결_업체/행수": len(group),
                "연결_업체명": " | ".join(group["업체명/사이트명"].astype(str).head(30)),
                "원본No목록": " | ".join(group["원본No"].astype(str).head(50)),
                "크롤링_필요정보/전략": first["크롤링_필요정보/전략"],
                "자동확인일": TODAY,
            }
        )
    df = df.drop(columns=["_summary_url_key"])
    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(["매물수_추정", "매물페이지여부"], ascending=[False, True]).reset_index(drop=True)
        summary_df["사이트순위"] = range(1, len(summary_df) + 1)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="unique_sites", index=False)
        df.to_excel(writer, sheet_name="site_rows", index=False)
        ws = writer.sheets["unique_sites"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ["A", "B", "C", "D", "E", "F", "G", "I", "J", "K", "L"]:
            ws.column_dimensions[col].width = 24 if col not in ["D", "F", "J", "L"] else 48
        ws = writer.sheets["site_rows"]
        widths = {
            "A": 8,
            "B": 10,
            "C": 10,
            "D": 28,
            "E": 22,
            "F": 38,
            "G": 42,
            "H": 48,
            "I": 12,
            "J": 42,
            "K": 22,
            "L": 28,
            "S": 38,
            "T": 58,
        }
        for col, width in widths.items():
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {csv_path}")
    print(f"WROTE {summary_csv_path}")
    print(f"WROTE {xlsx_path}")
    print(f"WROTE {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
