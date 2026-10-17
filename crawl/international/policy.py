from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from crawl.common import KST, clean_text


MIN_PRICE_KRW = 10_000_000

# These are deliberately coarse operational fallbacks, not live market quotes.
# Production can override every value in config.json. A stable fallback is safer
# than storing a foreign amount as KRW or accepting an unpriced listing.
DEFAULT_EXCHANGE_RATES_KRW = {
    "KRW": 1.0,
    "USD": 1_400.0,
    "EUR": 1_650.0,
    "GBP": 1_900.0,
    "CAD": 1_020.0,
    "AUD": 930.0,
    "NZD": 840.0,
    "CHF": 1_750.0,
    "CNY": 195.0,
    "JPY": 9.5,
    "SEK": 150.0,
    "NOK": 140.0,
    "DKK": 220.0,
    "PLN": 385.0,
    "CZK": 68.0,
    "TRY": 34.0,
    "AED": 382.0,
}

MACHINE_KEYWORDS = (
    "excavator", "digger", "backhoe", "loader", "skid steer", "forklift", "telehandler",
    "roller", "compactor", "compaction", "dozer", "bulldozer", "grader", "scraper",
    "crane", "aerial platform", "work platform", "boom lift", "scissor lift", "dumper",
    "dump truck", "drilling rig", "drill rig", "pile driver", "piling rig", "trencher",
    "paver", "asphalt machine", "asphalt distributor", "concrete pump", "concrete mixer",
    "batching plant", "concrete plant", "road construction", "mining equipment",
    "crawler tractor", "wheel tractor", "waste handler", "material handler",
)

NON_MACHINE_KEYWORDS = (
    "spare part", "spare parts", "replacement part", "construction part", "component",
    "attachment", "bucket", "quick coupler", "hydraulic breaker", "hammer attachment",
    "boom attachment", "undercarriage", "track chain", "tyre", "tire", "wheel rim",
    "engine", "gearbox", "transmission", "axle", "hydraulic pump", "hydraulic cylinder",
    "cabin", "cab assembly", "container", "office cabin", "scaffold", "formwork",
    "compressor", "generator", "lighting tower", "welding machine", "construction tool",
    "marine equipment", "oil and gas equipment",
)


@dataclass(frozen=True)
class InternationalPolicy:
    minimum_price_krw: int
    exchange_rates_krw: dict[str, float]
    exchange_rate_date: str

    def source_minimum(self, currency: str) -> int:
        rate = self.exchange_rates_krw.get(str(currency or "").upper())
        if rate is None or rate <= 0:
            raise ValueError(f"exchange rate is missing for {currency}")
        return max(1, math.ceil(self.minimum_price_krw / rate))


def _today_kst() -> str:
    return dt.datetime.now(KST).date().isoformat()


def load_policy(config_path: Path) -> InternationalPolicy:
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        raw = {}
    international = raw.get("international") if isinstance(raw, dict) else {}
    international = international if isinstance(international, dict) else {}

    rates = dict(DEFAULT_EXCHANGE_RATES_KRW)
    configured_rates = international.get("exchange_rates_krw")
    if isinstance(configured_rates, dict):
        for currency, value in configured_rates.items():
            try:
                rate = float(value)
            except (TypeError, ValueError):
                continue
            if rate > 0:
                rates[str(currency).upper()] = rate

    try:
        minimum = int(international.get("minimum_price_krw", MIN_PRICE_KRW))
    except (TypeError, ValueError):
        minimum = MIN_PRICE_KRW
    return InternationalPolicy(
        minimum_price_krw=max(MIN_PRICE_KRW, minimum),
        exchange_rates_krw=rates,
        exchange_rate_date=clean_text(international.get("exchange_rate_date")) or _today_kst(),
    )


def is_construction_machine(record: dict[str, Any]) -> bool:
    category = clean_text(record.get("category_name")).lower()
    title = clean_text(record.get("listing_name")).lower()
    description = clean_text(record.get("description")).lower()
    category_and_title = f"{category} {title}"
    if any(keyword in category_and_title for keyword in NON_MACHINE_KEYWORDS):
        # A concrete pump is a machine; a generic hydraulic pump is a part.
        if "concrete pump" not in category_and_title:
            return False
    searchable = f"{category_and_title} {description}"
    return any(keyword in searchable for keyword in MACHINE_KEYWORDS)


def prepare_record(
    record: dict[str, Any], policy: InternationalPolicy,
) -> tuple[dict[str, Any] | None, str | None]:
    if not is_construction_machine(record):
        return None, "non_construction_machine"

    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    if raw.get('machine_category_confirmed') is False:
        return None, 'unconfirmed_machine_category'
    if raw.get('price_kind') in ('auction_or_offer', 'unknown'):
        return None, 'not_asking_price'
    currency = clean_text(raw.get("currency")).upper()
    native_price = raw.get("native_price")
    try:
        native_amount = float(native_price)
    except (TypeError, ValueError):
        return None, "missing_price"
    if not math.isfinite(native_amount) or native_amount <= 0 or not currency:
        return None, "missing_price"
    rate = policy.exchange_rates_krw.get(currency)
    if rate is None or rate <= 0:
        return None, "missing_exchange_rate"

    price_krw = int(round(native_amount * rate))
    if price_krw < policy.minimum_price_krw:
        return None, "below_minimum_price"

    record["price_krw"] = price_krw
    record["sale_currency"] = currency
    record["sale_price"] = native_amount
    record["exchange_rate_krw"] = rate
    record["exchange_rate_date"] = policy.exchange_rate_date
    raw["currency"] = currency
    raw["native_price"] = native_amount
    raw["exchange_rate_krw"] = rate
    raw["exchange_rate_date"] = policy.exchange_rate_date
    raw["minimum_price_krw"] = policy.minimum_price_krw
    raw["price_krw"] = price_krw
    record["raw"] = raw
    return record, None


def filter_eligible_records(
    records: Iterable[dict[str, Any]], policy: InternationalPolicy,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    eligible: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    for record in records:
        prepared, reason = prepare_record(record, policy)
        if prepared is not None:
            eligible.append(prepared)
            continue
        key = reason or "unknown"
        rejected[key] = rejected.get(key, 0) + 1
    return eligible, rejected
