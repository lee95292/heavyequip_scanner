from __future__ import annotations

import hashlib
import re
import html
from urllib.parse import urlsplit
from typing import Any, Callable

from crawl.common import clean_text, date_string, datetime_string, parse_site_date, now_kst
from crawl.international.catalog import load_source_catalog


SOURCE_NAMES = {source['slug']: source['name'] for source in load_source_catalog()['sources']}


def plain_html(value: Any) -> str:
    return clean_text(html.unescape(re.sub(r'<[^>]*>', ' ', str(value or ''))))


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
        "crawled_at": datetime_string(now_kst()),
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
    adapted = dict(payload)
    if payload.get('equipId'):
        title = plain_html(payload.get('description'))
        path = urlsplit(str(payload.get('itemPageUri') or '')).path
        category = re.search(r'/for-sale/(.+?)-(?:19|20)\d{2}-', path)
        if not category:
            category = re.search(r'/for-sale/([^-]+)-', path)
        name = re.sub(r'^(?:19|20)\d{2}\s+', '', title)
        make = re.match(r'(?:New Holland|John Deere|FM Gru|[\w.-]+)', name)
        remainder = name[make.end():].strip() if make else ''
        # Preserve a source-observed model separately from model_norm. Unknown
        # title tokens must never be promoted into the trusted dictionary.
        model = re.match(r'((?:[A-Za-z]{2,8}\s+)?[A-Za-z0-9./-]*\d[A-Za-z0-9./-]*(?:\s+(?:RT|SR|LC|LCR|XLT|XL|LGP|CR))?)(?=\s|$)', remainder)
        price_kind = plain_html(payload.get('auctionType'))
        country = {'USA':'US','AUS':'AU','CAN':'CA','GBR':'GB','DEU':'DE','FRA':'FR',
                   'NLD':'NL','ITA':'IT','ESP':'ES','NZL':'NZ','ARE':'AE','JPN':'JP',
                   'CHN':'CN','MEX':'MX','POL':'PL','IRL':'IE','BEL':'BE','SWE':'SE'}.get(
                       str(payload.get('flagPath') or '').upper(), '')
        adapted.update(id=payload['equipId'], title=title, url=path,
                       category=category.group(1).replace('-', ' ') if category else '',
                       manufacturer=make.group(0) if make else None,
                       model=model.group(1) if model else None,
                       year=title[:4] if re.match(r'^(19|20)\d{2}\b',title) else None,
                       description=plain_html(payload.get('features')),
                       price=plain_html(payload.get('price')),
                       hours=payload.get('usage') if re.search(r'\b(?:hrs?|hours?)\b',str(payload.get('usage')),re.I) else None,
                       location=', '.join(filter(None,[plain_html(payload.get('eumeLocation')),country])),
                       saleType=price_kind)
    record = _common_record("ironplanet", adapted, "https://www.ironplanet.com")
    record['raw']['source'] = payload
    record['raw']['machine_category_confirmed'] = bool(re.search(
        r'excavator|loader|dozer|grader|forklift|telehandler|roller|compactor|crane|dumper|dump truck|paver|scraper|lift|drill|trencher|concrete',
        str(record.get('category_name') or ''), re.I))
    record['raw']['price_kind'] = 'asking' if plain_html(payload.get('auctionType')).lower() == 'buy now' else 'auction_or_offer'
    record['raw']['registration_date_basis'] = 'source' if record['posted_at'] else 'unavailable'
    record['raw']['model_origin'] = 'source_title_token_not_dictionary_entry'
    record["raw"]["ironclad_assurance"] = bool(_first(payload, "ironCladAssurance", "inspection.ironClad"))
    record["raw"]["auction_end_at"] = _first(payload, "auctionEndAt", "sale.endAt")
    return record


def _rb_auction(payload: dict[str, Any]) -> dict[str, Any]:
    return _common_record("rb_auction", payload, "https://www.rbauction.com")


def _plant_equipment(payload):
    record = _common_record('plant_equipment',payload,'https://www.plantandequipment.com')
    record['raw'].update(price_kind='asking',price_basis=payload.get('priceBasis'),
                         registration_date_basis='source' if record['posted_at'] else 'unavailable',
                         country=clean_text(payload.get('location')).rsplit(',',1)[-1].strip() or None)
    return record


def _europe_construction(payload):
    record = _common_record('europe_construction',payload,'https://www.europe-construction-equipment.com')
    record['raw'].update(price_kind='asking',price_basis=payload.get('priceBasis'),
                         registration_date_basis='source' if record['posted_at'] else 'unavailable')
    return record


def _mascus_global(payload: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(payload)
    adapted.update(
        {
            "id": _first(payload, "productId", "id"),
            "url": _first(payload, "assetUrl", "url"),
            "manufacturer": _first(payload, "brand", "manufacturer"),
            "model": _first(payload, "model", "modelName"),
            "year": _first(payload, "yearOfManufacture", "year"),
            "category": _first(payload, "categoryName", "category"),
            "price": _first(payload, "priceOriginal", "priceInUserCurrency", "price"),
            "currency": _first(payload, "priceOriginalUnit", "userCurrency", "currency"),
            "hours": _first(payload, "meterReadout", "hours"),
            "location": ", ".join(
                part for part in (
                    clean_text(payload.get("locationCity")),
                    clean_text(payload.get("locationCountryCode")),
                ) if part and part != "-"
            ),
            "sellerName": _first(payload, "companyName", "sellerName"),
            "phone": _first(payload, "sellerPhone", "phone"),
            "createdAt": _first(payload, "createDate", "createdAt"),
        }
    )
    record = _common_record("mascus_global", adapted, "https://www.mascus.com")
    record["raw"]["image_url"] = payload.get("imageUrl")
    return record


PARSERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "machinery_trader": _machinery_trader,
    "machineryline": _machineryline,
    "ironplanet": _ironplanet,
    "rb_auction": _rb_auction,
    "mascus_global": _mascus_global,
    'plant_equipment': _plant_equipment,
    'europe_construction': _europe_construction,
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
