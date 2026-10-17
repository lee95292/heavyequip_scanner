"""Source-backed CAT aliases and conservative token-boundary matching."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

CAT_PATH = Path(__file__).resolve().parents[1] / "docs" / "const" / "cat_models.json"
CAT_BRAND = re.compile(r"(?<![A-Z])(?:CATERPILLAR|CAT|캐터필러|캐터필라|카터필라)(?=$|[\s.®_-]|\d|[A-Z]{1,2}\d)", re.I)

def cat_entries() -> list[dict]:
    data = json.loads(CAT_PATH.read_text(encoding="utf-8"))
    entries = {}
    for group in data["groups"]:
        for code in group["models"]:
            compact = re.sub(r"\s+", "", code.upper())
            canonical = "CAT" + compact
            entries[canonical] = {"canonical": canonical, "alias": code.upper(), "source": group["source"], "category": group["category"]}
    return list(entries.values())

CAT_ENTRIES = cat_entries()

def cat_family_key(code: str) -> str:
    match = re.match(r"[A-Z]*\d+(?:\.\d+)?", code.upper().removeprefix("CAT"))
    return match.group(0) if match else ""

CAT_FAMILY_KEYS = {cat_family_key(entry["alias"]) for entry in CAT_ENTRIES}
CAT_ALIAS_KEYS = {re.sub(r"[^A-Z0-9]", "", entry["alias"]) for entry in CAT_ENTRIES}

def is_cat_family(code: str) -> bool:
    """Limit legacy aliases to families explicitly present in the CAT catalog."""
    return cat_family_key(code) in CAT_FAMILY_KEYS

@lru_cache(maxsize=4096)
def model_pattern(code: str) -> re.Pattern:
    # Split only letter/number transitions. E.g. '349 E' is valid, but
    # '349 Excavator' is not '349E'. Never erase boundaries between words.
    tokens = re.findall(r"[A-Z]+|\d+(?:\.\d+)*", code.upper())
    return re.compile(r"(?<![A-Z0-9.])" + r"[\s_-]*".join(re.escape(v) for v in tokens) + r"(?![A-Z0-9]|\.\d)", re.I)

def match_cat(value: Any, manufacturer: Any = None) -> str | None:
    text = str(value or "").upper()
    maker = str(manufacturer or "").strip()
    branded = bool(CAT_BRAND.search(text) or CAT_BRAND.search(maker))
    if maker and not branded:
        return None
    unbranded_text = CAT_BRAND.sub(" ", text)
    matches = []
    for entry in CAT_ENTRIES:
        code = entry["alias"]
        # Ambiguous bare numeric models need CAT manufacturer/brand context.
        # Exact standalone model fields remain usable when no maker is known.
        if not branded and re.fullmatch(r"[\d.]+", code) and not model_pattern(code).fullmatch(text.strip()):
            continue
        if model_pattern(code).search(unbranded_text):
            matches.append(entry["canonical"])
    return max(matches, key=len) if matches else None
