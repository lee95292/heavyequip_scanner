#!/usr/bin/env python3
import datetime as dt
import json
import re
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


ROOT = Path("/Users/myeonggyu/github/aetc/heavyequip-scanner")
SAMPLE_DIR = ROOT / "docs" / "sample"
RAW_DIR = SAMPLE_DIR / "raw"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "identity",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}


@dataclass
class Sample:
    slug: str
    site: str
    source_doc: str
    method: str
    display_url: str
    fetch_url: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)
    sample_headers: dict[str, str] = field(default_factory=dict)
    body: Optional[dict] = None
    response_type: str = "HTML"
    notes: list[str] = field(default_factory=list)
    fetch: bool = True

    @property
    def url(self) -> str:
        return self.fetch_url or self.display_url


SAMPLES = [
    Sample(
        slug="4396200_green_heavy",
        site="4396200.com 그린중기 공용매물",
        source_doc="../4396200.com.md",
        method="GET",
        display_url="https://www.4396200.com/sub8_1_s.html?cate_code=100100&limit=70&page=1",
        response_type="HTML",
        notes=["카테고리 `cate_code`와 페이지 `page`를 바꿔 순회합니다."],
    ),
    Sample(
        slug="jigecha_korea",
        site="지게차코리아 공용매물",
        source_doc="../jigecha.kr.md",
        method="GET",
        display_url="http://jigecha.kr/kwa-sell_jigecha?PB_1483420906=1",
        response_type="HTML",
        notes=["서브도메인 `imcg`, `wpjq`도 같은 엔진을 사용합니다."],
    ),
    Sample(
        slug="imcg_jigecha",
        site="imcg.jigecha.kr 지게차코리아 서브도메인",
        source_doc="../imcg.jigecha.kr.md",
        method="GET",
        display_url="http://imcg.jigecha.kr/kwa-sell_jigecha?PB_1483420906=1",
        response_type="HTML",
        notes=["같은 요청 계약을 쓰되 origin/source는 `imcg.jigecha.kr`로 분리합니다."],
    ),
    Sample(
        slug="wpjq_jigecha",
        site="wpjq.jigecha.kr 지게차코리아 서브도메인",
        source_doc="../wpjq.jigecha.kr.md",
        method="GET",
        display_url="http://wpjq.jigecha.kr/kwa-sell_jigecha?PB_1483420906=1",
        response_type="HTML",
        notes=["같은 요청 계약을 쓰되 origin/source는 `wpjq.jigecha.kr`로 분리합니다."],
    ),
    Sample(
        slug="ty_heavyequipment",
        site="태양중기매매상사",
        source_doc="../ty-heavyequipment.com.md",
        method="GET",
        display_url="https://ty-heavyequipment.com/taeyang_product_list/?cat1=18&taeyang_custom=15&paged=1",
        response_type="HTML",
        notes=["상세는 같은 엔드포인트에 `id` 파라미터를 붙여 접근합니다."],
    ),
    Sample(
        slug="2963566_seoul",
        site="서울중기매매상사",
        source_doc="../2963566.com.md",
        method="GET",
        display_url="https://www.2963566.com/bbs/board.php?bo_table=m20011&page=1",
        response_type="HTML",
        notes=["그누보드 게시판 구조이며 상세는 `wr_id`로 구분됩니다."],
    ),
    Sample(
        slug="3dump_samsung",
        site="삼성중기매매상사",
        source_doc="../3dump.co.kr.md",
        method="GET",
        display_url="https://www.3dump.co.kr/bbs/board.php?bo_table=m01_01&ca_id=20b0&p=1",
        response_type="HTML",
        notes=["일부 상세 링크는 `onclick` 속성 안에 있으므로 속성 파싱이 필요합니다."],
    ),
    Sample(
        slug="4833_sunwoo",
        site="선우중장비매매상사",
        source_doc="../4833.com.md",
        method="GET",
        display_url="http://www.4833.com/Machine/RecomList.asp?MType=18&page=1",
        response_type="HTML",
        notes=["ASP 기반 목록이며 상세는 `Idx`로 구분됩니다."],
    ),
    Sample(
        slug="perfect82",
        site="퍼펙트82중장비",
        source_doc="../../site_api_param_analysis/perfect82.md",
        method="GET",
        display_url="https://www.perfect82.com/fnew100",
        response_type="HTML",
        notes=["매물 수 100건 기준으로 API 분석 목록에 포함되어 있어 샘플도 함께 보관합니다."],
    ),
    Sample(
        slug="mascus_korea",
        site="Mascus Korea",
        source_doc="../mascus.co.kr.md",
        method="POST",
        display_url="https://qhqraq9hm7.execute-api.eu-central-1.amazonaws.com/Search/SearchAssets",
        headers={
            "Content-Type": "application/json",
            "hostname": "www.mascus.co.kr",
            "reqfor": "env:browser:for:searchResults",
        },
        body={
            "catalogs": ["construction"],
            "countries": ["KR"],
            "pagesize": 2,
            "page": 1,
            "usercurrency": "KRW",
        },
        response_type="JSON",
        notes=["샘플 응답 크기를 줄이기 위해 `pagesize=2`로 요청합니다."],
    ),
    Sample(
        slug="junggi114",
        site="중기114",
        source_doc="../중기114.com.md",
        method="GET",
        display_url="https://중기114.com/product?page=1",
        fetch_url="https://xn--114-vg9le98h.com/product?page=1",
        response_type="HTML",
        notes=["실제 요청은 IDNA punycode host로 보내고 문서에는 한글 도메인을 함께 남깁니다."],
    ),
    Sample(
        slug="band_69640559",
        site="BAND www.band.us/band/69640559",
        source_doc="../www.band.us_band_69640559.md",
        method="GET",
        display_url="https://api-kr.band.us/v2.0.0/get_posts_and_announcements?ts={TIMESTAMP_MS}&band_no=69640559&resolution_type=4&order_by=created_at_desc",
        fetch_url="https://api-kr.band.us/v2.0.0/get_posts_and_announcements?ts=1777562655507&band_no=69640559&resolution_type=4&order_by=created_at_desc",
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": "https://www.band.us",
            "Referer": "https://www.band.us/band/69640559/post",
            "language": "ko",
        },
        sample_headers={
            "akey": "${BAND_AKEY}",
            "md": "${BAND_MD}",
            "Cookie": "BBC=${BAND_BBC}; di=${BAND_DI}; band_session=${BAND_SESSION}; as=${BAND_AS}; ai=${BAND_AI}; language=ko",
        },
        response_type="JSON",
        notes=[
            "Open API `access_token`이 아니라 웹 세션 쿠키와 서명 헤더가 필요한 내부 API입니다.",
            "민감한 쿠키/헤더 값은 저장하지 않고 환경변수 placeholder로만 표기합니다.",
            "샘플 응답은 비인증 호출 결과이므로 성공 응답 스키마가 아니라 인증 실패 응답일 수 있습니다.",
        ],
    ),
]


def decode_body(raw: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([^;\s]+)", content_type, re.I)
    encodings = []
    if charset_match:
        encodings.append(charset_match.group(1).strip("\"'"))
    encodings.extend(["utf-8", "cp949", "euc-kr", "latin-1"])
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def truncate_text(text: str, limit: int = 8000) -> str:
    text = text.replace("```", "``\u200b`")
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... [truncated, original {len(text):,} chars]"


def json_excerpt(text: str, limit: int = 12000) -> tuple[str, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return truncate_text(text, limit), "text"

    if isinstance(data, dict):
        compact = {}
        for key, value in data.items():
            if isinstance(value, list):
                compact[key] = value[:2]
                if len(value) > 2:
                    compact[f"{key}__truncated_count"] = len(value)
            elif isinstance(value, dict):
                compact[key] = {
                    nested_key: (nested_value[:2] if isinstance(nested_value, list) else nested_value)
                    for nested_key, nested_value in list(value.items())[:20]
                }
            else:
                compact[key] = value
        return truncate_text(json.dumps(compact, ensure_ascii=False, indent=2), limit), "json"

    if isinstance(data, list):
        return truncate_text(json.dumps(data[:2], ensure_ascii=False, indent=2), limit), "json"

    return truncate_text(json.dumps(data, ensure_ascii=False, indent=2), limit), "json"


def curl_command(sample: Sample) -> str:
    parts = ["curl -L"]
    if sample.method.upper() != "GET":
        parts.append(f"-X {sample.method.upper()}")
    parts.append(repr(sample.display_url))
    headers = {}
    headers.update(sample.headers)
    headers.update(sample.sample_headers)
    for key, value in headers.items():
        if key.lower() == "cookie":
            parts.append(f"-b {value!r}")
        else:
            parts.append(f"-H {f'{key}: {value}'!r}")
    if sample.body is not None:
        parts.append(f"--data {json.dumps(sample.body, ensure_ascii=False)!r}")
    return " \\\n  ".join(parts)


def actual_curl_command(sample: Sample) -> str:
    parts = ["curl -L"]
    if sample.method.upper() != "GET":
        parts.append(f"-X {sample.method.upper()}")
    parts.append(repr(sample.url))
    headers = dict(DEFAULT_HEADERS)
    headers.update(sample.headers)
    for key, value in headers.items():
        parts.append(f"-H {f'{key}: {value}'!r}")
    if sample.body is not None:
        parts.append(f"--data {json.dumps(sample.body, ensure_ascii=False)!r}")
    return " \\\n  ".join(parts)


def response_extension(content_type: str) -> str:
    lower = content_type.lower()
    if "json" in lower:
        return "json"
    if "html" in lower:
        return "html"
    if "xml" in lower:
        return "xml"
    return "txt"


def fetch_sample(sample: Sample) -> dict:
    body_bytes = None
    headers = dict(DEFAULT_HEADERS)
    headers.update(sample.headers)
    if sample.body is not None:
        body_bytes = json.dumps(sample.body, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        sample.url,
        data=body_bytes,
        headers=headers,
        method=sample.method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            return {
                "status": response.status,
                "url": response.geturl(),
                "content_type": content_type,
                "response_headers": dict(response.headers.items()),
                "raw_body": raw,
                "body": decode_body(raw, content_type),
                "body_length": len(raw),
            }
    except urllib.error.HTTPError as error:
        raw = error.read()
        content_type = error.headers.get("Content-Type", "")
        return {
            "status": error.code,
            "url": sample.url,
            "content_type": content_type,
            "response_headers": dict(error.headers.items()),
            "raw_body": raw,
            "body": decode_body(raw, content_type),
            "body_length": len(raw),
            "error": str(error),
        }
    except Exception as error:
        body = f"{type(error).__name__}: {error}"
        return {
            "status": None,
            "url": sample.url,
            "content_type": "",
            "response_headers": {},
            "raw_body": body.encode("utf-8"),
            "body": body,
            "body_length": 0,
            "error": str(error),
        }


def write_raw_files(sample: Sample, result: dict, generated_at: str) -> Path:
    directory = RAW_DIR / sample.slug
    directory.mkdir(parents=True, exist_ok=True)

    (directory / "request.curl").write_text(actual_curl_command(sample) + "\n", encoding="utf-8")
    if sample.sample_headers:
        (directory / "request.authenticated.redacted.curl").write_text(
            curl_command(sample) + "\n",
            encoding="utf-8",
        )
    if sample.body is not None:
        (directory / "request_body.json").write_text(
            json.dumps(sample.body, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    header_lines = [f"HTTP status: {result['status']}"]
    for key, value in result.get("response_headers", {}).items():
        header_lines.append(f"{key}: {value}")
    (directory / "response_headers.txt").write_text("\n".join(header_lines) + "\n", encoding="utf-8")

    ext = response_extension(result.get("content_type", ""))
    body_name = f"response_body.{ext}"
    (directory / body_name).write_bytes(result.get("raw_body", b""))

    metadata = {
        "site": sample.site,
        "slug": sample.slug,
        "generated_at": generated_at,
        "method": sample.method.upper(),
        "request_url": sample.url,
        "display_url": sample.display_url,
        "status": result["status"],
        "final_url": result["url"],
        "content_type": result["content_type"],
        "body_length": result["body_length"],
        "response_body_file": body_name,
        "error": result.get("error"),
        "notes": sample.notes,
        "sensitive_values_stored": False,
    }
    (directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return directory


def write_sample(sample: Sample, result: dict, generated_at: str) -> Path:
    body, language = json_excerpt(result["body"])
    if language == "text" and "html" in result.get("content_type", "").lower():
        language = "html"

    notes = "\n".join(f"- {note}" for note in sample.notes) if sample.notes else "- 없음"
    lines = [
        f"# {sample.site} 샘플 요청/응답",
        "",
        f"- 생성일: {generated_at}",
        f"- 기준 문서: [{sample.source_doc}]({sample.source_doc})",
        f"- 응답 유형: {sample.response_type}",
        f"- 요청 URL: `{sample.display_url}`",
        "",
        "## 요청",
        "",
        "```bash",
        curl_command(sample),
        "```",
        "",
        "## 응답 샘플",
        "",
        f"- HTTP status: `{result['status']}`",
        f"- 최종 URL: `{result['url']}`",
        f"- Content-Type: `{result['content_type']}`",
        f"- 원본 응답 크기: `{result['body_length']:,}` bytes",
    ]
    if result.get("error"):
        lines.append(f"- 호출 메모: `{result['error']}`")
    lines.extend(
        [
            "",
            f"```{language}",
            body,
            "```",
            "",
            "## 수집 메모",
            "",
            notes,
            "",
        ]
    )
    path = SAMPLE_DIR / f"{sample.slug}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_raw_index(raw_paths: list[Path], generated_at: str) -> None:
    lines = [
        "# 실제 요청/응답 원문",
        "",
        f"- 생성일: {generated_at}",
        "- 각 디렉터리는 실제 실행한 요청과 응답 원문을 보관합니다.",
        "- `request.curl`: 실제 실행한 요청입니다.",
        "- `response_headers.txt`: 실제 응답 상태와 헤더입니다.",
        "- `response_body.*`: 실제 응답 본문 원문입니다.",
        "- `metadata.json`: 요청/응답 메타데이터입니다.",
        "- Band 인증 쿠키/헤더 값은 저장하지 않았습니다. 인증 재현용 파일은 placeholder가 들어간 `request.authenticated.redacted.curl`입니다.",
        "",
    ]
    for path in raw_paths:
        lines.append(f"- [{path.name}/]({path.name}/)")
    (RAW_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_index(paths: list[Path], generated_at: str) -> None:
    lines = [
        "# 사이트별 샘플 요청/응답",
        "",
        f"- 생성일: {generated_at}",
        "- 요청/응답 샘플은 크롤러 구현 시 엔드포인트, 필수 파라미터, 응답 형태를 빠르게 확인하기 위한 자료입니다.",
        "- Band 인증 쿠키/헤더처럼 민감한 값은 저장하지 않고 placeholder로만 표기했습니다.",
        "- 실제 요청/응답 원문: [raw/INDEX.md](raw/INDEX.md)",
        "",
    ]
    for path in paths:
        lines.append(f"- [{path.name}]({path.name})")
    (SAMPLE_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    generated_at = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S %Z")
    paths = []
    raw_paths = []
    for sample in SAMPLES:
        result = fetch_sample(sample)
        raw_path = write_raw_files(sample, result, generated_at)
        path = write_sample(sample, result, generated_at)
        raw_paths.append(raw_path)
        paths.append(path)
        print(f"{sample.slug}: {result['status']} -> {path} / {raw_path}")
    write_raw_index(raw_paths, generated_at)
    write_index(paths, generated_at)
    print(RAW_DIR / "INDEX.md")
    print(SAMPLE_DIR / "INDEX.md")


if __name__ == "__main__":
    main()
