#!/usr/bin/env python3
import json
import re
import urllib.parse
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup


warnings.filterwarnings("ignore", message="Unverified HTTPS request")

OUT_DIR = Path("site_api_param_analysis")
OUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
}

SITES = [
    {
        "slug": "4396200_green_heavy",
        "name": "4396200.com 그린중기 공용매물",
        "url": "https://www.4396200.com/sub8_1_s.html?cate_code=100100",
        "count_estimate": 7700,
        "platform_hosts": ["4396200.com", "www.4396200.com"],
    },
    {
        "slug": "jigecha_korea",
        "name": "지게차코리아 공용매물",
        "url": "http://jigecha.kr/kwa-sell_jigecha",
        "count_estimate": 7392,
        "platform_hosts": ["jigecha.kr", "www.jigecha.kr", "imcg.jigecha.kr", "wpjq.jigecha.kr"],
    },
    {
        "slug": "ty_heavyequipment",
        "name": "태양중기매매상사",
        "url": "https://ty-heavyequipment.com/taeyang_product_list/?cat1=18",
        "count_estimate": 1522,
        "platform_hosts": ["ty-heavyequipment.com"],
    },
    {
        "slug": "2963566_seoul",
        "name": "서울중기매매상사",
        "url": "https://www.2963566.com/bbs/board.php?bo_table=m20011",
        "count_estimate": 179,
        "platform_hosts": ["2963566.com", "www.2963566.com"],
    },
    {
        "slug": "3dump_samsung",
        "name": "삼성중기매매상사",
        "url": "https://www.3dump.co.kr/bbs/board.php?bo_table=m01_01&ca_id=20b0",
        "count_estimate": 118,
        "platform_hosts": ["3dump.co.kr", "www.3dump.co.kr"],
    },
    {
        "slug": "4833_sunwoo",
        "name": "선우중장비매매상사",
        "url": "http://www.4833.com/Machine/RecomList.asp?MType=18",
        "count_estimate": 101,
        "platform_hosts": ["4833.com", "www.4833.com"],
    },
    {
        "slug": "perfect82",
        "name": "퍼펙트82중장비",
        "url": "https://www.perfect82.com/fnew100",
        "count_estimate": 100,
        "platform_hosts": ["perfect82.com", "www.perfect82.com"],
    },
]


def fetch(session, url):
    r = session.get(url, headers=HEADERS, timeout=20, verify=False, allow_redirects=True)
    return r


def canonical_host(url):
    return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")


def parse_query(url):
    parsed = urllib.parse.urlparse(url)
    return {k: v for k, v in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items()}


def urls_from_element(el, base_url):
    urls = []
    if el.name == "a" and el.get("href"):
        urls.append(urllib.parse.urljoin(base_url, el.get("href").strip()))
    onclick = el.get("onclick") or ""
    for m in re.finditer(r"(?:location\.href|window\.location(?:\.href)?)\s*=\s*['\"]([^'\"]+)['\"]", onclick):
        urls.append(urllib.parse.urljoin(base_url, m.group(1)))
    return urls


def form_info(soup, base_url):
    forms = []
    for idx, form in enumerate(soup.find_all("form"), 1):
        method = (form.get("method") or "GET").upper()
        action = urllib.parse.urljoin(base_url, form.get("action") or base_url)
        fields = []
        for control in form.find_all(["input", "select", "textarea", "button"]):
            name = control.get("name")
            if not name:
                continue
            item = {
                "name": name,
                "tag": control.name,
                "type": control.get("type", ""),
                "value": control.get("value", ""),
                "label": "",
            }
            if control.name == "select":
                item["options_sample"] = [
                    {"value": opt.get("value", ""), "text": opt.get_text(" ", strip=True)}
                    for opt in control.find_all("option")[:12]
                ]
            fields.append(item)
        text = re.sub(r"\s+", " ", form.get_text(" ", strip=True))[:200]
        forms.append({"index": idx, "method": method, "action": action, "fields": fields, "text_sample": text})
    return forms


def link_param_info(soup, base_url, hosts):
    rows = []
    path_counter = Counter()
    param_counter = Counter()
    samples_by_path = defaultdict(list)
    detail_patterns = Counter()
    category_links = []
    page_links = []
    allowed_hosts = [h.replace("www.", "") for h in hosts]
    for el in soup.find_all(True):
        for url in urls_from_element(el, base_url):
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                continue
            if url.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            host = parsed.netloc.lower()
            if hosts and host.replace("www.", "") not in allowed_hosts:
                continue
            params = parse_query(url)
            path_counter[parsed.path] += 1
            for p in params:
                param_counter[p] += 1
            text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))[:160]
            sample = {"text": text, "url": url, "params": params}
            if len(samples_by_path[parsed.path]) < 6:
                samples_by_path[parsed.path].append(sample)
            lowered = {p.lower(): p for p in params}
            if any(p.startswith("PB_") for p in params) or any(k in lowered for k in ["page", "paged", "p", "pageno", "page_no"]):
                page_links.append(sample)
            if any(
                p.startswith("SCH_category_") or p in ["cate_code", "cat1", "cat2", "ca_id", "MType", "bo_table", "bcate", "scate", "MType"]
                for p in params
            ):
                category_links.append(sample)
            if any(p.lower() in ["pid", "wr_id", "idx", "product_no", "no", "seq", "uid", "id"] for p in params) or re.search(
                r"_v-\d+|/view/|/read/", parsed.path, re.I
            ):
                detail_patterns[parsed.path] += 1
            rows.append(sample)
    top_paths = [
        {"path": path, "count": count, "samples": samples_by_path[path]}
        for path, count in path_counter.most_common(15)
    ]
    return {
        "top_paths": top_paths,
        "param_frequency": dict(param_counter.most_common(30)),
        "category_link_samples": category_links[:30],
        "pagination_link_samples": page_links[:30],
        "detail_path_frequency": dict(detail_patterns.most_common(15)),
    }


def script_info(soup, base_url):
    script_srcs = []
    inline_text = []
    for script in soup.find_all("script"):
        if script.get("src"):
            script_srcs.append(urllib.parse.urljoin(base_url, script.get("src")))
        elif script.string:
            inline_text.append(script.string)
    joined = "\n".join(inline_text)
    endpoint_patterns = []
    regexes = [
        r"(?:fetch|axios\.(?:get|post)|\$\.(?:ajax|get|post))\s*\(\s*['\"]([^'\"]+)",
        r"url\s*:\s*['\"]([^'\"]+)",
        r"['\"]([^'\"]*(?:ajax|api|json|load|search|list|get|post)[^'\"]*)['\"]",
    ]
    for rx in regexes:
        for m in re.finditer(rx, joined, re.I):
            val = m.group(1)
            if len(val) <= 220:
                endpoint_patterns.append(urllib.parse.urljoin(base_url, val))
    return {
        "script_srcs_sample": script_srcs[:40],
        "inline_endpoint_hints": sorted(set(endpoint_patterns))[:80],
        "inline_script_count": len(inline_text),
        "external_script_count": len(script_srcs),
    }


def sample_pages(session, site, soup, base_url):
    samples = []
    seen = set()
    links = link_param_info(soup, base_url, site["platform_hosts"])
    for item in links["pagination_link_samples"][:3] + links["category_link_samples"][:5]:
        url = item["url"]
        if url in seen:
            continue
        seen.add(url)
        try:
            r = fetch(session, url)
            samples.append(
                {
                    "url": url,
                    "status": r.status_code,
                    "content_type": r.headers.get("content-type", ""),
                    "bytes": len(r.content),
                    "title": BeautifulSoup(r.text, "html.parser").title.get_text(strip=True)
                    if BeautifulSoup(r.text, "html.parser").title
                    else "",
                }
            )
        except Exception as e:
            samples.append({"url": url, "error": f"{type(e).__name__}: {e}"})
    return samples


def infer_contract(site, page, soup, links, forms, scripts):
    parsed = urllib.parse.urlparse(page["final_url"])
    current_params = parse_query(page["final_url"])
    all_params = Counter()
    for form in forms:
        for field in form["fields"]:
            all_params[field["name"]] += 2
    for k, v in links["param_frequency"].items():
        all_params[k] += v

    response_type = "HTML"
    if "json" in (page["content_type"] or "").lower():
        response_type = "JSON/API"
    elif scripts["inline_endpoint_hints"]:
        response_type = "HTML 목록 + JS/Ajax 단서"

    observed_names = [k for k, _ in all_params.most_common(80)]

    def has_param(*names):
        wanted = {n.lower() for n in names}
        return [p for p in observed_names if p.lower() in wanted or any(p.startswith(n) for n in names if n.endswith("_"))]

    pagination_params = []
    for p in observed_names:
        lp = p.lower()
        if lp in ["page", "paged", "p", "pageno", "page_no"] or p.startswith("PB_") or p == "Page":
            pagination_params.append(p)
    category_params = []
    for p in observed_names:
        lp = p.lower()
        if lp in ["cate_code", "cat1", "cat2", "ca_id", "mtype", "bo_table", "gr_id", "bcate", "scate"] or p.startswith(
            "SCH_category_"
        ):
            category_params.append(p)
    search_params = []
    for p in observed_names:
        lp = p.lower()
        if (
            lp
            in [
                "find",
                "find1",
                "find2",
                "find3",
                "find4",
                "search",
                "stx",
                "sfl",
                "sop",
                "syear",
                "eyear",
                "mkco",
                "maker",
                "model",
                "area",
                "price",
                "min_price",
                "max_price",
                "category",
                "keyword",
                "q",
                "smaker",
                "mimaker",
                "mmodel",
                "msort",
                "search_value",
                "skeyword",
            ]
            or p.startswith("SCH_")
        ):
            search_params.append(p)
    detail_params = []
    for p in observed_names:
        if p.lower() in ["pid", "wr_id", "idx", "it_id", "product_no", "no", "seq", "uid", "id"] or p == "Idx":
            detail_params.append(p)
    if links["detail_path_frequency"] and not detail_params:
        detail_params.append("path_suffix_id")

    return {
        "base_endpoint": urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", "")),
        "current_query_params": current_params,
        "observed_param_names_ranked": observed_names[:40],
        "response_type": response_type,
        "likely_pagination_params": list(dict.fromkeys(pagination_params)),
        "likely_category_params": list(dict.fromkeys(category_params)),
        "likely_search_filter_params": list(dict.fromkeys(search_params)),
        "likely_detail_id_params": list(dict.fromkeys(detail_params)),
    }


def write_markdown(site, page, contract, forms, links, scripts, page_samples):
    md_path = OUT_DIR / f"{site['slug']}.md"
    json_path = OUT_DIR / f"{site['slug']}.json"

    lines = []
    lines.append(f"# {site['name']}")
    lines.append("")
    lines.append(f"- 확인 URL: `{page['final_url']}`")
    lines.append(f"- 매물 수 추정: `{site['count_estimate']}`")
    lines.append(f"- 응답 형식 판단: `{contract['response_type']}`")
    lines.append(f"- 기본 목록 엔드포인트: `{contract['base_endpoint']}`")
    lines.append(f"- 현재 Query: `{json.dumps(contract['current_query_params'], ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 요청 파라미터 요약")
    lines.append("")
    lines.append(f"- 카테고리/게시판: `{', '.join(contract['likely_category_params']) or '미확인'}`")
    lines.append(f"- 페이지네이션: `{', '.join(contract['likely_pagination_params']) or '미확인'}`")
    lines.append(f"- 검색/필터: `{', '.join(contract['likely_search_filter_params']) or '미확인'}`")
    lines.append(f"- 상세 ID: `{', '.join(contract['likely_detail_id_params']) or '미확인'}`")
    lines.append("")
    lines.append("## 관찰된 파라미터 빈도")
    lines.append("")
    for name, count in list(links["param_frequency"].items())[:30]:
        lines.append(f"- `{name}`: {count}")
    if not links["param_frequency"]:
        lines.append("- 링크 query 파라미터가 거의 없거나 path 기반입니다.")
    lines.append("")
    lines.append("## 폼 분석")
    lines.append("")
    if forms:
        for form in forms:
            fields = ", ".join(f"`{f['name']}`" for f in form["fields"][:30])
            lines.append(f"- Form {form['index']}: `{form['method']}` `{form['action']}`")
            lines.append(f"  - fields: {fields or '없음'}")
            if form["text_sample"]:
                lines.append(f"  - text: {form['text_sample']}")
    else:
        lines.append("- form 없음")
    lines.append("")
    lines.append("## 주요 경로/샘플")
    lines.append("")
    for item in links["top_paths"][:10]:
        lines.append(f"- `{item['path']}`: {item['count']} links")
        for sample in item["samples"][:3]:
            lines.append(f"  - `{sample['text']}` -> `{sample['url']}`")
    lines.append("")
    lines.append("## 페이지네이션 샘플")
    lines.append("")
    if links["pagination_link_samples"]:
        for sample in links["pagination_link_samples"][:10]:
            lines.append(f"- `{sample['text']}` -> `{sample['url']}`")
    else:
        lines.append("- 페이지네이션 링크 미검출")
    lines.append("")
    lines.append("## 카테고리 샘플")
    lines.append("")
    if links["category_link_samples"]:
        for sample in links["category_link_samples"][:12]:
            lines.append(f"- `{sample['text']}` -> `{sample['url']}`")
    else:
        lines.append("- 카테고리 링크 미검출")
    lines.append("")
    lines.append("## 스크립트/API 단서")
    lines.append("")
    lines.append(f"- 외부 스크립트 수: `{scripts['external_script_count']}`")
    lines.append(f"- 인라인 스크립트 수: `{scripts['inline_script_count']}`")
    if scripts["inline_endpoint_hints"]:
        for hint in scripts["inline_endpoint_hints"][:25]:
            lines.append(f"- `{hint}`")
    else:
        lines.append("- 명시적인 JSON/API 엔드포인트 미검출")
    lines.append("")
    lines.append("## 검증 요청 샘플")
    lines.append("")
    for sample in page_samples:
        lines.append(
            f"- `{sample.get('status', '')}` `{sample.get('content_type', '')}` `{sample.get('bytes', '')}` -> `{sample.get('url')}`"
        )
    lines.append("")
    lines.append("## 크롤링 메모")
    lines.append("")
    lines.append("- 우선순위: 목록 URL의 query 파라미터를 조합해 페이지 단위 HTML을 수집한 뒤 상세 링크를 따라가는 방식.")
    lines.append("- JSON API로 바로 응답하는 패턴은 현재 확인 페이지 기준 미검출. 스크립트 단서는 대부분 UI/검색 보조 또는 범용 AJAX로 보이며, 실제 매물 목록은 초기 HTML에 포함됩니다.")
    lines.append("- 필수 추출 필드 후보: 상세URL, 제목/모델명, 제조사, 연식, 가격, 지역, 판매상/연락처, 등록일, 조회수, 카테고리, 거래상태.")

    data = {
        "site": site,
        "page": page,
        "request_contract": contract,
        "forms": forms,
        "links": links,
        "scripts": scripts,
        "page_samples": page_samples,
    }
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path


def main():
    session = requests.Session()
    index_rows = []
    for site in SITES:
        r = fetch(session, site["url"])
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        page = {
            "requested_url": site["url"],
            "final_url": r.url,
            "status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
            "bytes": len(r.content),
            "title": title,
        }
        forms = form_info(soup, r.url)
        links = link_param_info(soup, r.url, site["platform_hosts"])
        scripts = script_info(soup, r.url)
        samples = sample_pages(session, site, soup, r.url)
        contract = infer_contract(site, page, soup, links, forms, scripts)
        md_path, json_path = write_markdown(site, page, contract, forms, links, scripts, samples)
        index_rows.append((site, page, contract, md_path, json_path))
        print(f"WROTE {md_path} {json_path}")

    index_lines = ["# 중장비 매물 사이트 API/요청 파라미터 분석", ""]
    index_lines.append("|순위|사이트|매물수 추정|응답|기본 엔드포인트|파일|")
    index_lines.append("|---:|---|---:|---|---|---|")
    for i, (site, page, contract, md_path, json_path) in enumerate(index_rows, 1):
        index_lines.append(
            f"|{i}|{site['name']}|{site['count_estimate']}|{contract['response_type']}|`{contract['base_endpoint']}`|[{md_path.name}]({md_path.name}) / [{json_path.name}]({json_path.name})|"
        )
    index_lines.append("")
    index_lines.append("기준: `heavy_equipment_unique_sites_sorted_2026-04-29.csv`에서 매물 수 추정 100건 이상 사이트.")
    (OUT_DIR / "INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"WROTE {OUT_DIR / 'INDEX.md'}")


if __name__ == "__main__":
    main()
