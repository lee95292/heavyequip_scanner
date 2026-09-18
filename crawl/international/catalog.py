from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).resolve().parents[2] / "docs" / "international_sources.json"


@lru_cache(maxsize=1)
def load_source_catalog() -> dict[str, Any]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload.get("sources"), list):
        raise ValueError("international source catalog must contain a sources list")
    return payload


def source_by_slug(slug: str) -> dict[str, Any]:
    for source in load_source_catalog()["sources"]:
        if source.get("slug") == slug:
            return source
    raise KeyError(f"unknown international source: {slug}")
