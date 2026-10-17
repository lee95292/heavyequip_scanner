from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass
from typing import Any, Optional

from prediction.config import PredictionSettings
from prediction.model_name import (
    ModelNameResolver,
    ModelResolution,
    build_seed_catalog,
    decode_json_object,
    normalize_model_name,
)
from prediction.warehouse import WarehouseRepository


HOUR_KEYS = ("가동시간", "사용시간", "작업시간", "운전시간", "누적시간", "사용 시간", "시간")
NUMBER_PATTERN = r"(?<![\d.,])(\d[\d,]*(?:\.\d+)?)(?![\d.,])"


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _safe_number(value: Any) -> Optional[float]:
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def parse_price_krw(value: Any, fallback_text: Any = None) -> Optional[int]:
    text = clean_text(fallback_text if fallback_text not in (None, "") else value)
    if not text or any(word in text for word in ("협의", "문의", "상담")):
        return None
    total = 0.0
    eok = re.search(rf"{NUMBER_PATTERN}\s*억", text)
    man = re.search(rf"{NUMBER_PATTERN}\s*만(?:원)?", text)
    if eok:
        amount = _safe_number(eok.group(1))
        total += (amount or 0.0) * 100_000_000
    if man:
        amount = _safe_number(man.group(1))
        total += (amount or 0.0) * 10_000
    if total > 0 and math.isfinite(total):
        return int(total)
    if not math.isfinite(total):
        return None
    try:
        direct = int(float(str(value).replace(",", "")))
        if direct > 0:
            return direct
    except (TypeError, ValueError, OverflowError):
        pass
    number = re.search(NUMBER_PATTERN, text)
    if not number:
        return None
    amount = _safe_number(number.group(1))
    if amount is None:
        return None
    if "천원" in text:
        amount *= 1_000
    elif "원" not in text and amount < 1_000_000:
        # Heavy-equipment boards commonly omit the unit and use 만원.
        amount *= 10_000
    return int(amount) if amount > 0 else None


def parse_manufactured_ym(value: Any, *, today: Optional[dt.date] = None) -> tuple[Optional[int], Optional[int]]:
    text = clean_text(value)
    if not text:
        return None, None
    match = re.search(r"(?<!\d)(\d{2,4})\s*(?:[./년-]\s*(\d{1,2}))?", text)
    if not match:
        return None, None
    year = int(match.group(1))
    current_year = (today or dt.date.today()).year
    if year < 100:
        pivot = (current_year + 1) % 100
        year += 2000 if year <= pivot else 1900
    month = int(match.group(2)) if match.group(2) else None
    if year < 1970 or year > current_year + 1:
        return None, None
    if month is not None and not 1 <= month <= 12:
        month = None
    return year, month


def _hours_from_text(value: Any, *, key_confirms_hours: bool = False) -> Optional[float]:
    text = clean_text(value).upper()
    if not text:
        return None
    if any(unit in text for unit in ("KM", "키로", "킬로")) and not re.search(r"시간|HOUR|HRS?|HR", text):
        return None
    ten_thousand = re.search(
        rf"{NUMBER_PATTERN}\s*만\s*(?:시간|HOURS?|HRS?|HR|H)?",
        text,
    )
    if ten_thousand and (key_confirms_hours or re.search(r"시간|HOUR|HRS?|HR|H", text)):
        amount = _safe_number(ten_thousand.group(1))
        if amount is None:
            return None
        hours = amount * 10_000
    else:
        unit_pattern = r"시간|HOURS?|HRS?|HR" if not key_confirms_hours else r"시간|HOURS?|HRS?|HR|H"
        pattern = rf"{NUMBER_PATTERN}\s*(?:{unit_pattern})"
        match = re.search(pattern, text)
        if not match and key_confirms_hours:
            match = re.search(NUMBER_PATTERN, text)
        if not match:
            return None
        amount = _safe_number(match.group(1))
        if amount is None:
            return None
        hours = amount
    return hours if 0 <= hours <= 200_000 else None


def extract_operating_hours(row: dict[str, Any]) -> Optional[float]:
    raw = decode_json_object(row.get("raw_json"))
    detail = raw.get("detail") if isinstance(raw.get("detail"), dict) else {}
    for key, value in detail.items():
        normalized_key = clean_text(key)
        if any(candidate in normalized_key for candidate in HOUR_KEYS):
            hours = _hours_from_text(value, key_confirms_hours=True)
            if hours is not None:
                return hours
        if normalized_key == "운행":
            hours = _hours_from_text(value)
            if hours is not None:
                return hours
    for value in (row.get("description"),):
        hours = _hours_from_text(value)
        if hours is not None:
            return hours
    return None


def raw_detail(row: dict[str, Any]) -> dict[str, Any]:
    raw = decode_json_object(row.get("raw_json"))
    detail = raw.get("detail")
    return detail if isinstance(detail, dict) else {}


def normalize_identity(value: Any, *, contact: bool = False) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    if contact:
        digits = re.sub(r"\D", "", text)
        if digits.startswith("82") and len(digits) >= 11:
            digits = "0" + digits[2:]
        return digits
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def dedupe_hash(identity: Any, price_krw: int, model_name: str, *, contact: bool = False) -> Optional[str]:
    normalized = normalize_identity(identity, contact=contact)
    if not normalized:
        return None
    payload = f"{normalized}|{int(price_krw)}|{model_name}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def owner_group_hash(
    seller: Any,
    contact: Any,
    _model_name: str,
    _source_listing_id: int,
) -> Optional[str]:
    contact_key = normalize_identity(contact, contact=True)
    seller_key = normalize_identity(seller)
    if contact_key:
        payload = f"contact|{contact_key}"
    elif seller_key:
        payload = f"seller|{seller_key}"
    else:
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_detail_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parsed = urllib.parse.urlparse(text)
    tracking_keys = {"fbclid", "gclid", "ref", "referer"}
    query_items = [
        (key, item)
        for key, item in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in tracking_keys
    ]
    compact_query = urllib.parse.urlencode(sorted(query_items))
    return urllib.parse.urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", compact_query, ""))


def entity_group_hash(row: dict[str, Any], model_name: str, year: int, seller: Any, contact: Any) -> str:
    source_site = clean_text(row.get("source_site"))
    pid = clean_text(row.get("pid"))
    if pid:
        payload = f"pid|{source_site}|{pid}"
    else:
        detail_url = canonical_detail_url(row.get("detail_url"))
        if detail_url:
            payload = f"url|{detail_url}"
        else:
            identity = normalize_identity(contact, contact=True) or normalize_identity(seller)
            payload = f"fallback|{identity}|{model_name}|{year}|{row.get('source_listing_id')}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _seller_and_contact(row: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    detail = raw_detail(row)
    seller = clean_text(detail.get("상호") or row.get("seller")) or None
    contact = clean_text(detail.get("연락처") or row.get("contact")) or None
    return seller, contact


@dataclass(frozen=True)
class CleanCandidate:
    row: Optional[dict[str, Any]]
    status: str
    message: Optional[str]


def build_clean_candidate(
    raw_row: dict[str, Any],
    resolution: ModelResolution,
    settings: PredictionSettings,
) -> CleanCandidate:
    source_listing_id = int(raw_row["source_listing_id"])
    if not resolution.model_name or resolution.confidence < settings.model_confidence_threshold:
        return CleanCandidate(
            None,
            "needs_review",
            f"model confidence {resolution.confidence:.4f} below {settings.model_confidence_threshold:.4f}",
        )
    price_krw = parse_price_krw(raw_row.get("price_krw"), raw_row.get("price"))
    if price_krw is None or not settings.price_min_krw <= price_krw <= settings.price_max_krw:
        return CleanCandidate(None, "rejected", "missing or out-of-range price")
    year, month = parse_manufactured_ym(raw_row.get("manufactured_ym"))
    if year is None:
        return CleanCandidate(None, "rejected", "missing or invalid manufactured year")
    seller, contact = _seller_and_contact(raw_row)
    row = {
        "source_listing_id": source_listing_id,
        "pid": clean_text(raw_row.get("pid")) or None,
        "detail_url": clean_text(raw_row.get("detail_url")) or None,
        "manufactured_year": year,
        "manufactured_month": month,
        "model_name_raw": clean_text(raw_row.get("model_name")) or None,
        "model_norm": normalize_model_name(raw_row.get("model_norm")) or None,
        "model_name_clean": resolution.model_name,
        "model_confidence": round(float(resolution.confidence), 6),
        "cleaning_method": resolution.method,
        "price_krw": price_krw,
        "operating_hours": extract_operating_hours(raw_row),
        "manufacturer": clean_text(raw_row.get("manufacturer")) or None,
        "category_code": clean_text(raw_row.get("category_code")) or None,
        "category_name": clean_text(raw_row.get("category_name")) or None,
        "equipment_status": clean_text(raw_row.get("status")) or None,
        "source_site": clean_text(raw_row.get("source_site")) or None,
        "location": clean_text(raw_row.get("location")) or None,
        "seller": seller,
        "contact": contact,
        "seller_dedupe_hash": dedupe_hash(seller, price_krw, resolution.model_name),
        "contact_dedupe_hash": dedupe_hash(contact, price_krw, resolution.model_name, contact=True),
        "owner_group_hash": owner_group_hash(seller, contact, resolution.model_name, source_listing_id),
        "entity_group_hash": entity_group_hash(raw_row, resolution.model_name, year, seller, contact),
        "listing_name": clean_text(raw_row.get("listing_name")) or None,
        "posted_at": raw_row.get("posted_at") or raw_row.get("posted_date"),
        # Use the first source observation for stable chronological splitting.
        "crawled_at": raw_row.get("source_created_at") or raw_row.get("crawled_at"),
    }
    return CleanCandidate(row, "cleaned", None)


def run_cleaning(
    settings: PredictionSettings,
    *,
    recheck_needs_review: bool = False,
) -> dict[str, Any]:
    started_at = dt.datetime.now()
    with WarehouseRepository(settings) as repository:
        run_id = repository.create_cleaning_run(started_at)
        stats: dict[str, Any] = {
            "run_id": run_id,
            "started_at": started_at.isoformat(),
            "seed_model_count": 0,
            "processed_count": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "duplicate_count": 0,
            "review_count": 0,
            "rejected_count": 0,
        }
        try:
            all_rows = repository.fetch_all_raw()
            catalog = build_seed_catalog(all_rows, settings.min_model_frequency)
            stats["seed_model_count"] = len(catalog)
            repository.replace_model_catalog(catalog)
            resolver = ModelNameResolver(catalog, settings.random_seed).fit(all_rows)
            resolver_path = settings.artifact_dir / "cleaning" / "model_name_resolver.joblib"
            resolver.save(resolver_path)
            catalog_path = settings.artifact_dir / "cleaning" / "model_dictionary.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            catalog_path.chmod(0o600)

            candidates = repository.fetch_cleaning_candidates(
                recheck_needs_review=recheck_needs_review
            )
            with repository.connection.cursor() as cursor:
                for raw_row in candidates:
                    stats["processed_count"] += 1
                    source_id = int(raw_row["source_listing_id"])
                    try:
                        resolution = resolver.resolve(raw_row)
                        candidate = build_clean_candidate(raw_row, resolution, settings)
                    except (TypeError, ValueError, OverflowError) as error:
                        repository.remove_cleaned(cursor, source_id)
                        repository.mark_raw(
                            cursor,
                            source_id,
                            "rejected",
                            f"row normalization error: {type(error).__name__}",
                        )
                        stats["rejected_count"] += 1
                        continue
                    if candidate.row is None:
                        repository.remove_cleaned(cursor, source_id)
                        repository.mark_raw(cursor, source_id, candidate.status, candidate.message)
                        if candidate.status == "needs_review":
                            stats["review_count"] += 1
                        else:
                            stats["rejected_count"] += 1
                        continue
                    clean_action = repository.upsert_cleaned(cursor, candidate.row)
                    if clean_action in {"inserted", "updated"}:
                        stats[f"{clean_action}_count"] += 1
                        repository.mark_raw(cursor, source_id, "cleaned", resolution.method)
                    else:
                        stats["duplicate_count"] += 1
                        repository.mark_raw(
                            cursor,
                            source_id,
                            "duplicate",
                            "seller/contact + price + model duplicate",
                        )
            stats["resolver_path"] = str(resolver_path)
            stats["completed_at"] = dt.datetime.now().isoformat()
            repository.finish_cleaning_run(run_id, "done", stats)
            return stats
        except BaseException as error:
            stats["error"] = f"{type(error).__name__}: {error}"
            stats["completed_at"] = dt.datetime.now().isoformat()
            repository.finish_cleaning_run(run_id, "failed", stats)
            raise
