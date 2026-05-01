# python3 crawl/interfacae.py --site green_heavy --mode 전체 --sleep 0.3

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.common import CrawlConfig, DEFAULT_CONFIG_PATH, DEFAULT_OUTPUT_DIR, load_mysql_config, normalize_mode


# 프록시를 코드에서 고정하려면 여기에 값을 넣으세요.
# 예: HARDCODED_PROXY = "http://user:password@127.0.0.1:8080"
HARDCODED_PROXY = ""#"http://qsllgyur-1:jcg3t0l7bk4z@p.webshare.io:80"


SITE_REGISTRY = {
    "green_heavy": {
        "module": "crawl.site.green_heavy",
        "origins": {"4396200.com", "www.4396200.com", "https://4396200.com", "https://www.4396200.com"},
    }
}


def site_for_origin(origin: str) -> str:
    normalized = origin.strip().lower().rstrip("/")
    for site, meta in SITE_REGISTRY.items():
        if normalized in meta["origins"]:
            return site
    raise ValueError(f"지원하지 않는 origin입니다: {origin}")


def resolve_sites(args: argparse.Namespace) -> list[str]:
    sites = set(args.site or [])
    for origin in args.origin or []:
        sites.add(site_for_origin(origin))
    if not sites:
        sites = set(SITE_REGISTRY.keys())
    return sorted(sites)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="중장비 매물 크롤러 실행 인터페이스")
    parser.add_argument("--mode", default="1d", help="실행 모드: 전체/all, 최근1일/1d, 최근5일/5d, 1달/1m")
    parser.add_argument("--sleep", type=float, default=0.3, help="요청 간 기본 sleep 초. 기본값 0.3")
    parser.add_argument("--origin", action="append", help="크롤링 대상 origin. 예: 4396200.com")
    parser.add_argument("--site", action="append", choices=sorted(SITE_REGISTRY), help="크롤링 대상 사이트 slug")
    parser.add_argument("--proxy", help="프록시 URL. 지정하지 않으면 interface.py의 HARDCODED_PROXY 사용")
    parser.add_argument("--max-pages", type=int, help="테스트용 카테고리당 최대 페이지 수")
    parser.add_argument("--max-categories", type=int, help="테스트용 최대 카테고리 수")
    parser.add_argument("--max-items", type=int, help="테스트용 최대 저장 매물 수")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="파싱 JSON 출력 디렉터리")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="DB 연결 설정 JSON 경로")
    parser.add_argument("--no-db", action="store_true", help="DB 적재 없이 JSON 파일만 생성")
    return parser


def run(args: argparse.Namespace) -> dict:
    mode = normalize_mode(args.mode)
    config = CrawlConfig(
        mode=mode,
        sleep_seconds=args.sleep,
        origins=tuple(args.origin or ()),
        proxy=args.proxy or HARDCODED_PROXY or None,
        output_dir=args.output_dir,
        mysql=load_mysql_config(args.config),
        max_pages=args.max_pages,
        max_categories=args.max_categories,
        max_items=args.max_items,
        write_db=not args.no_db,
    )
    summary = {"mode": mode, "sites": []}
    for site in resolve_sites(args):
        module = importlib.import_module(SITE_REGISTRY[site]["module"])
        result = module.run(config)
        summary["sites"].append(result)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
