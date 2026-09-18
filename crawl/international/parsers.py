from __future__ import annotations

import hashlib
import re
from typing import Any, Callable

from crawl.common import clean_text, date_string, datetime_string, parse_site_date


SOURCE_NAMES = {
    "machinery_trader": "Machinery Trader",
    "machineryline": "Machineryline",
    "ironplanet": "IronPlanet",
}


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value: Any = payload
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, "", [], {}):
            return value
    return None


def _number(value: Any) -> int | float | None:
    match = re.search(r"-?[\d,.]+", clean_text(value))
    if not match:
        return None
    normalized = match.group(0).replace(",", "")
    try:
        number = float(normalized)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _currency(payload: dict[str, Any], price_text: str) -> str | None:
    explicit = _first(payload, "currency", "price.currency", "priceCurrency")
    if explicit:
        return clean_text(explicit).upper()
    symbols = {"$": "USD", "€": "EUR", "£": "GBP", "CAD": "CAD", "AUD": "AUD"}
    upper = price_text.upper()
    for token, currency in symbols.items():
        if token in upper:
            return currency
    return None


def _common_record(site_slug: str, payload: dict[str, Any], origin: str) -> dict[str, Any]:
    detail_url = clean_text(_first(payload, "url", "detailUrl", "canonicalUrl") or "")
    if detail_url.startswith("/"):
        detail_url = origin.rstrip("/") + detail_url
    price_value = _first(payload, "price", "displayPrice", "pricing.amount", "currentPrice")
    price_text = clean_text(price_value)
    posted = parse_site_date(clean_text(_first(payload, "postedAt", "updatedAt", "datePosted", "createdAt") or ""))
    manufacturer = clean_text(_first(payload, "manufacturer", "make", "brand.name", "brand") or "")
    model = clean_text(_first(payload, "model", "modelName") or "")
    year = _first(payload, "year", "modelYear", "manufactureYear")
    category = clean_text(_first(payload, "category", "categoryName", "type") or "")
    title = clean_text(_first(payload, "title", "name") or f"{year or ''} {manufacturer} {model}")
    listing_id = clean_text(_first(payload, "id", "listingId", "itemId", "stockNumber") or detail_url)
    record = {
        "origin": origin,
        "source_site": SOURCE_NAMES[site_slug],
        "crawl_url": clean_text(_first(payload, "crawlUrl") or ""),
        "detail_url": detail_url,
        "pid": listing_id[:64] or None,
        "category_code": clean_text(_first(payload, "categoryId", "categoryCode") or "") or None,
        "category_name": category or None,
        "listing_name": title or None,
        "model_name": model or None,
        "description": clean_text(_first(payload, "description", "summary") or "") or None,
        "price": price_text or None,
        # A native foreign-currency amount must never be treated as KRW before conversion.
        "price_krw": None,
        "contact": clean_text(_first(payload, "phone", "seller.phone", "contact") or "") or None,
        "posted_date": date_string(posted),
        "posted_at": datetime_string(posted),
        "manufacturer": manufacturer or None,
        "manufactured_ym": str(year) if year not in (None, "") else None,
        "location": clean_text(_first(payload, "location", "location.name", "machineLocation") or "") or None,
        "seller": clean_text(_first(payload, "seller.name", "sellerName", "dealer") or "") or None,
        "status": clean_text(_first(payload, "condition", "saleType", "status") or "") or None,
        "raw": {
            "site_slug": site_slug,
            "currency": _currency(payload, price_text),
            "native_price": _number(price_value),
            "operating_hours": _number(_first(payload, "hours", "meter", "operatingHours")),
            "sale_type": clean_text(_first(payload, "saleType", "buyingFormat") or "") or None,
            "source": payload,
        },
    }
    # International listings are mutable (price, auction state, description). Use
    # the source identity so a later capture updates the row instead of duplicating it.
    identity = f"{site_slug}:{listing_id or detail_url}"
    record["content_hash"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return record


def _machinery_trader(payload: dict[str, Any]) -> dict[str, Any]:
    return _common_record("machinery_trader", payload, "https://www.machinerytrader.com")


def _machineryline(payload: dict[str, Any]) -> dict[str, Any]:
    return _common_record("machineryline", payload, "https://machineryline.com")


def _ironplanet(payload: dict[str, Any]) -> dict[str, Any]:
    record = _common_record("ironplanet", payload, "https://www.ironplanet.com")
    record["raw"]["ironclad_assurance"] = bool(_first(payload, "ironCladAssurance", "inspection.ironClad"))
    record["raw"]["auction_end_at"] = _first(payload, "auctionEndAt", "sale.endAt")
    return record


PARSERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "machinery_trader": _machinery_trader,
    "machineryline": _machineryline,
    "ironplanet": _ironplanet,
}


def parse_listing_payload(site_slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize one captured listing object without making an external request."""
    try:
        parser = PARSERS[site_slug]
    except KeyError as error:
        raise ValueError(f"unsupported international parser: {site_slug}") from error
    if not isinstance(payload, dict):
        raise TypeError("listing payload must be a dictionary")
    return parser(payload)
