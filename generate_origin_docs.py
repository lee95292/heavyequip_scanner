#!/usr/bin/env python3
import datetime as dt
import json
import re
import urllib.parse
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/myeonggyu/github/aetc/heavyequip-scanner")
DETAIL_CSV = ROOT / "heavy_equipment_sites_inventory_sorted_2026-04-29.csv"
ORIGINAL_CSV = Path("/Users/myeonggyu/Downloads/korea_heavy_equipment_keyword_homepage_expanded_v2_2026-04-19.csv")
API_DIR = ROOT / "site_api_param_analysis"
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)

MANUAL_ORIGIN_DOCS = [
    "mascus.co.kr.md",
    "중기114.com.md",
]
MANUAL_PLATFORM_ORIGIN_DOCS = [
    "www.band.us_band_69640559.md",
]


def origin_key(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url))
    scheme = parsed.scheme or "http"
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{scheme}://{host}"


def origin_host(origin: str) -> str:
    return urllib.parse.urlparse(origin).netloc


def safe_file_name(host: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", host).strip("_") + ".md"


def load_api(slug: str) -> dict:
    with (API_DIR / f"{slug}.json").open("r", encoding="utf-8") as f:
        return json.load(f)


API_BY_ORIGIN = {
    "https://4396200.com": ("4396200_green_heavy", "https://www.4396200.com/sub8_1_s.html"),
    "http://jigecha.kr": ("jigecha_korea", "http://jigecha.kr/kwa-sell_jigecha"),
    "http://imcg.jigecha.kr": ("jigecha_korea", "http://imcg.jigecha.kr/kwa-sell_jigecha"),
    "http://wpjq.jigecha.kr": ("jigecha_korea", "http://wpjq.jigecha.kr/kwa-sell_jigecha"),
    "https://ty-heavyequipment.com": (
        "ty_heavyequipment",
        "https://ty-heavyequipment.com/taeyang_product_list/",
    ),
    "https://2963566.com": ("2963566_seoul", "https://www.2963566.com/bbs/board.php"),
    "https://3dump.co.kr": ("3dump_samsung", "https://www.3dump.co.kr/bbs/board.php"),
    "http://4833.com": ("4833_sunwoo", "http://www.4833.com/Machine/RecomList.asp"),
}


SITE_META = {
    "https://4396200.com": {
        "site_name": "4396200.com",
        "display_name": "그린중기 공용매물",
        "equipment": "굴삭기, 덤프트럭/추레라, 믹서트럭/펌프카, 지게차, 압롤/진게/물차, 카고/탑차, 크레인, 로더/도자, 피니셔/롤러, 콤푸/드릴/항타기, 크락샤/플랜트, 기타건설기계",
        "operator_note": "원본 CSV의 그린중기(주) 행 기준: 대표자 노아영, 대표전화 02-439-6200, 상담전화 010-6665-6200, 사업자등록번호 217-81-29356.",
        "period_note": "등록일 기준 기간 파라미터는 확인되지 않았습니다. `syear`, `eyear`는 장비 연식 범위로 보입니다.",
    },
    "http://jigecha.kr": {
        "site_name": "jigecha.kr",
        "display_name": "지게차코리아 공용매물",
        "equipment": "중고 지게차 중심. 디젤식, 전동좌식, 전동입식, 톤수/제조사/지역별 지게차, 지게차 타이어, 배터리, 신차, 물류장비, 부품 메뉴 확인.",
        "operator_note": "플랫폼 운영사 대표자 정보는 원본 CSV에서 분리 확인되지 않았습니다. 연결된 업체 행에는 광성중기매매상사, 금일중기매매상사, 대구중기매매상사, 대왕중기매매상사, 두산건기매매상사 등이 포함됩니다.",
        "period_note": "`SCH_open_date_1_year/month`, `SCH_open_date_2_year/month`가 기간/연식 범위 필터로 쓰입니다. 등록일 전용 파라미터인지는 추가 검증이 필요합니다.",
    },
    "http://imcg.jigecha.kr": {
        "site_name": "imcg.jigecha.kr",
        "display_name": "지게차코리아 서브도메인 공용매물",
        "equipment": "jigecha.kr과 같은 지게차코리아 매물 체계를 사용합니다. 중고 지게차, 디젤/전동 지게차, 부품/타이어/배터리 관련 메뉴 확인.",
        "operator_note": "원본 CSV 연결 업체는 제일중기매매상사, 중기맨입니다. 플랫폼 자체 대표자 정보는 미확인입니다.",
        "period_note": "`SCH_open_date_1_year/month`, `SCH_open_date_2_year/month`가 기간/연식 범위 필터로 쓰입니다. 등록일 전용 파라미터인지는 추가 검증이 필요합니다.",
    },
    "http://wpjq.jigecha.kr": {
        "site_name": "wpjq.jigecha.kr",
        "display_name": "지게차코리아 서브도메인 공용매물",
        "equipment": "jigecha.kr과 같은 지게차코리아 매물 체계를 사용합니다. 중고 지게차, 디젤/전동 지게차, 부품/타이어/배터리 관련 메뉴 확인.",
        "operator_note": "원본 CSV 연결 업체는 청룡중장비매매상사입니다. 대표전화 041-855-6585, 취급품목은 굴삭기/지게차/덤프트럭 매입·매매로 기록되어 있습니다.",
        "period_note": "`SCH_open_date_1_year/month`, `SCH_open_date_2_year/month`가 기간/연식 범위 필터로 쓰입니다. 등록일 전용 파라미터인지는 추가 검증이 필요합니다.",
    },
    "https://ty-heavyequipment.com": {
        "site_name": "ty-heavyequipment.com",
        "display_name": "태양중기매매상사",
        "equipment": "굴착기/어태치부속, 덤프트럭/셀프로다, 지게차/하이랜더, 압롤/진게/물차, 카고/냉동/탑차, 크레인/카고크레인, 로더/도저/페이로더, 피니셔/롤러, 콤푸/드릴/항타기, 크락샤/배차플랜트, 기타건설기계, 트렉터/농기계",
        "operator_note": "원본 CSV 기준: 태양중기매매상사, 대표자 민경래, 대표전화 1566-1329, 상담전화 010-5413-8949, 사업자등록번호 122-01-42006, 소재지 인천광역시 계양구.",
        "period_note": "등록일 기준 기간 파라미터는 확인되지 않았습니다. `syear`, `eyear`는 장비 연식 범위로 보입니다.",
    },
    "https://2963566.com": {
        "site_name": "2963566.com",
        "display_name": "서울중기매매상사",
        "equipment": "건설기계/중장비 매매. 확인 엔드포인트는 추레라 게시판이며, 메뉴/검색 필터에서 제작사와 연식 범위 조건 확인.",
        "operator_note": "원본 CSV 기준: 서울중기매매상사, 대표자 방성진 / 방운혁(페이지별 상이 표기), 대표전화 010-5296-3566 / 010-2600-3566, 사업자등록번호 110-09-69139, 소재지 서울시 마포구.",
        "period_note": "`wr_2_start`, `wr_2_end`가 연식 시작/끝 필터로 확인됩니다. 등록일 기준 기간 파라미터는 미확인입니다.",
    },
    "https://3dump.co.kr": {
        "site_name": "3dump.co.kr",
        "display_name": "삼성중기매매상사",
        "equipment": "믹서트럭/펌프카, 덤프트럭/추레라, 굴삭기/어태치먼트, 지게차/하이랜더, 압롤/살수차/진게차, 카고트럭/냉동차/탑차, 크레인, 로더/도자/그레다, 휘니샤/로울러, 기타건설기계, 굴삭기/기타 장비부속",
        "operator_note": "원본 CSV 기준: 삼성중기매매상사, 대표자 박영대, 대표전화 010-5842-1233, 사업자등록번호 417-41-10811, 주소는 의정부/구리 표기가 병행됩니다.",
        "period_note": "검색 폼에서 등록일/기간 파라미터는 확인되지 않았습니다.",
    },
    "http://4833.com": {
        "site_name": "4833.com",
        "display_name": "선우중장비매매상사",
        "equipment": "굴삭기, 로우더, 운반차/추레라/셀프로더/살수차, 덤프트럭, 지게차/고소작업차, 불도저, 레미콘/콘크리트장비, 크레인, 도로포장장비, 특수장비, 작업장치/부속, 기타",
        "operator_note": "원본 CSV 기준: 선우중장비매매상사, 대표자 정우용, 대표전화 041-544-4833, 사업자등록번호 312-12-45015, 소재지 충남 예산군.",
        "period_note": "검색 폼에서 등록일/기간 파라미터는 확인되지 않았습니다.",
    },
}


def one_line_values(series, limit=12):
    values = []
    for value in series.dropna().astype(str):
        if value and value != "nan" and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return values


def param_list(values):
    return ", ".join(f"`{v}`" for v in values) if values else "미확인"


def md_for_origin(origin, group, api_data):
    meta = SITE_META[origin]
    contract = api_data["request_contract"]
    endpoint = API_BY_ORIGIN[origin][1]
    count = int(group["매물수_추정"].max())
    checked_urls = one_line_values(group["확인한_매물페이지URL"], 5)
    companies = one_line_values(group["업체명/사이트명"], 20)
    phones = one_line_values(group["원본_대표전화"], 10)
    source_items = [f"{name}" for name in companies]
    page_params = contract.get("likely_pagination_params", [])
    category_params = contract.get("likely_category_params", [])
    search_params = contract.get("likely_search_filter_params", [])
    detail_params = contract.get("likely_detail_id_params", [])
    current_query = contract.get("current_query_params", {})
    if origin.startswith("http://") and "jigecha.kr" in origin:
        current_query = {}

    example_query = {}
    example_query.update({k: v for k, v in current_query.items()})
    if "jigecha.kr" in origin:
        example_query = {"PB_1483420906": ["2"]}
    elif origin == "https://4396200.com":
        example_query = {"cate_code": ["100100"], "limit": ["70"], "page": ["2"]}
    elif origin == "https://ty-heavyequipment.com":
        example_query = {"cat1": ["18"], "taeyang_custom": ["15"], "paged": ["2"]}
    elif origin == "https://2963566.com":
        example_query = {"bo_table": ["m20011"], "page": ["2"]}
    elif origin == "https://3dump.co.kr":
        example_query = {"bo_table": ["m01_01"], "ca_id": ["20b0"], "p": ["2"]}
    elif origin == "http://4833.com":
        example_query = {"MType": ["18"], "page": ["2"]}

    encoded_query = urllib.parse.urlencode(
        [(k, item) for k, vals in example_query.items() for item in (vals if isinstance(vals, list) else [vals])]
    )
    example_url = endpoint + (("?" + encoded_query) if encoded_query else "")

    lines = [
        f"# {meta['site_name']}",
        "",
        "## 개요",
        "",
        f"- 사이트명: {meta['display_name']}",
        f"- Origin: `{origin}`",
        f"- 사이트 내 매물 수: 약 `{count:,}`건",
        f"- 확인한 대표 매물 URL: {', '.join(f'`{u}`' for u in checked_urls)}",
        f"- 취급장비 정보: {meta['equipment']}",
        f"- 대표자/운영자 정보: {meta['operator_note']}",
    ]
    if source_items:
        lines.append(f"- 연결된 원본 업체: {', '.join(source_items)}")
    if phones:
        lines.append(f"- 원본 CSV 대표전화: {', '.join(phones)}")

    lines.extend(
        [
            "",
            "## API 정보",
            "",
            "- API 성격: JSON API가 아니라 `HTML 목록 엔드포인트`입니다. `requests + BeautifulSoup` 방식으로 목록 HTML을 받아 매물 행과 상세 URL을 파싱하는 구조입니다.",
            f"- 단일 API 엔드포인트: `{endpoint}`",
            "- HTTP 메서드: `GET` 중심. 일부 검색 폼은 `POST`로도 제출되지만, 목록 URL은 쿼리 파라미터 조합으로 재현 가능합니다.",
            f"- 카테고리/게시판 파라미터: {param_list(category_params)}",
            f"- 페이지네이션 파라미터: {param_list(page_params)}",
            f"- 검색/필터 파라미터: {param_list(search_params)}",
            f"- 상세 매물 식별자: {param_list(detail_params)}",
            f"- 기간 파라미터: {meta['period_note']}",
            f"- 예시 요청: `{example_url}`",
        ]
    )

    lines.extend(
        [
            "",
            "## 특이사항",
            "",
        ]
    )

    if "jigecha.kr" in origin:
        lines.extend(
            [
                "- 상세 매물은 query id가 아니라 `/kwa-sell_jigecha_v-{id}` 경로 패턴으로 연결됩니다.",
                "- 같은 지게차코리아 엔진이 여러 서브도메인에 배포되어 있으므로, 이 문서는 해당 origin만 대상으로 합니다.",
                "- 단일 엔드포인트에서 목록은 가져올 수 있지만 검색 폼은 hidden 필드(`board`, `flag`, `Q_STRING`, `P_SELF`, `VG_live_code`)를 함께 보내는 구조라 POST 검색 재현 시 세션/hidden 값 보존이 필요할 수 있습니다.",
            ]
        )
    elif origin == "https://4396200.com":
        lines.extend(
            [
                "- `www.4396200.com`과 `4396200.com`은 같은 사이트로 정규화했습니다.",
                "- 상세 URL은 `/sub8_1_vvv.html?pid=...&redir=...` 패턴입니다.",
                "- 카테고리가 매우 많으므로 전체 수집은 `cate_code` 목록을 먼저 수집한 뒤 카테고리별 `page`를 순회하는 방식이 안정적입니다.",
            ]
        )
    elif origin == "https://ty-heavyequipment.com":
        lines.extend(
            [
                "- 목록과 상세가 같은 `/taeyang_product_list/` 엔드포인트를 사용하며, 상세는 `id` 파라미터로 구분됩니다.",
                "- `taeyang_custom`은 페이지당 노출 수로 보이며 15/30/50/100 옵션이 확인됩니다.",
                "- 사이트 내 스크립트/Ajax 단서는 있으나 매물 목록은 초기 HTML에 포함됩니다.",
            ]
        )
    elif origin == "https://2963566.com":
        lines.extend(
            [
                "- 그누보드 계열 게시판 구조입니다. 게시판은 `bo_table`, 상세는 `wr_id`로 구분됩니다.",
                "- 확인 매물 수는 `m20011` 추레라 게시판 기준입니다. 다른 장비 게시판까지 전체 수집하려면 사이트 내 `bo_table` 목록을 추가 수집해야 합니다.",
            ]
        )
    elif origin == "https://3dump.co.kr":
        lines.extend(
            [
                "- 그누보드 계열 게시판 구조입니다. 카테고리는 `ca_id`, 상세는 `wr_id`로 구분됩니다.",
                "- 일부 상세 링크가 `<a href>`가 아니라 `onclick=\"location.href='...'\"` 안에 들어 있으므로 HTML 속성까지 파싱해야 합니다.",
            ]
        )
    elif origin == "http://4833.com":
        lines.extend(
            [
                "- ASP 기반 HTML 목록입니다. 추천매물은 `/Machine/RecomList.asp`, 전체 사용자 매물은 `/Machine/UserList.asp`에도 존재합니다.",
                "- 상세는 `/Machine/recomView.asp?Page=...&Idx=...&MType=...` 패턴입니다.",
                "- 원본 카운트는 추천매물 기준 101건입니다. 전체보기 링크에는 더 큰 수치가 있으나 현재 문서는 등록 매물 수가 검증된 추천매물 엔드포인트를 기준으로 작성했습니다.",
            ]
        )
    else:
        lines.append("- 예외 사항 없음.")

    return "\n".join(lines) + "\n"


def main():
    detail = pd.read_csv(DETAIL_CSV)
    original = pd.read_csv(ORIGINAL_CSV, encoding="utf-8-sig")
    detail["origin"] = detail["확인한_매물페이지URL"].map(origin_key)

    written = []
    for origin, group in detail.groupby("origin"):
        max_count = int(group["매물수_추정"].max())
        if max_count <= 100:
            continue
        if origin not in API_BY_ORIGIN:
            continue
        slug, _endpoint = API_BY_ORIGIN[origin]
        api_data = load_api(slug)
        doc = md_for_origin(origin, group.sort_values("매물수_추정", ascending=False), api_data)
        path = DOCS_DIR / safe_file_name(origin_host(origin))
        path.write_text(doc, encoding="utf-8")
        written.append(path)

    manual_origin_paths = [
        DOCS_DIR / name for name in MANUAL_ORIGIN_DOCS if (DOCS_DIR / name).exists()
    ]
    manual_platform_origin_paths = [
        DOCS_DIR / name for name in MANUAL_PLATFORM_ORIGIN_DOCS if (DOCS_DIR / name).exists()
    ]
    origin_index_paths = sorted(written + manual_origin_paths)

    index_lines = ["# Origin별 중장비 매물 수집 문서", ""]
    index_lines.append("- 기준: 등록 매물 수 추정치가 100건을 초과하는 origin")
    index_lines.append("- `www.`는 같은 사이트로 정규화")
    index_lines.append("- CSV 외 웹 조사 및 플랫폼 예외 origin 포함")
    index_lines.append("- 샘플 요청/응답: [sample/INDEX.md](sample/INDEX.md)")
    index_lines.append("")
    index_lines.append("## 100건 초과 Origin")
    index_lines.append("")
    for path in origin_index_paths:
        index_lines.append(f"- [{path.name}]({path.name})")
    if manual_platform_origin_paths:
        index_lines.append("")
        index_lines.append("## 플랫폼 예외 Origin")
        index_lines.append("")
        for path in sorted(manual_platform_origin_paths):
            index_lines.append(f"- [{path.name}]({path.name})")
    (DOCS_DIR / "INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print("WROTE")
    for path in origin_index_paths + sorted(manual_platform_origin_paths):
        print(path)
    print(DOCS_DIR / "INDEX.md")


if __name__ == "__main__":
    main()
