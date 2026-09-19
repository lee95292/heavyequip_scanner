from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import requests


ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
FX_CACHE_PATH = Path(__file__).resolve().parent / "data" / "fx_rates.json"
INTERNATIONAL_SOURCE_NAMES = {
    "Machineryline",
    "Mascus Global",
    "Machinery Trader",
    "IronPlanet",
    "Ritchie Bros. Auctioneers",
}
_SNAPSHOT_CACHE: dict[str, tuple[int, "FxSnapshot | None"]] = {}


@dataclass(frozen=True)
class FxSnapshot:
    rate_date: str
    rates_krw: dict[str, Decimal]
    source_url: str = ECB_DAILY_URL


def parse_ecb_xml(payload: str | bytes) -> FxSnapshot:
    root = ET.fromstring(payload)
    rate_date = ""
    quoted: dict[str, Decimal] = {"EUR": Decimal("1")}
    for element in root.iter():
        time_value = element.attrib.get("time")
        if time_value:
            rate_date = time_value
        currency = str(element.attrib.get("currency") or "").upper()
        rate = element.attrib.get("rate")
        if currency and rate:
            quoted[currency] = Decimal(rate)
    if not rate_date or "KRW" not in quoted:
        raise ValueError("ECB response did not contain a dated KRW reference rate")
    krw_per_eur = quoted["KRW"]
    rates = {currency: krw_per_eur / units_per_eur for currency, units_per_eur in quoted.items()}
    rates["KRW"] = Decimal("1")
    return FxSnapshot(rate_date=rate_date, rates_krw=rates)


def fetch_ecb_snapshot(timeout: int = 20) -> FxSnapshot:
    user_agent = "HeavyEquipScanner/1.0 (+https://scan.mglee.dev)"
    try:
        response = requests.get(
            ECB_DAILY_URL,
            headers={"User-Agent": user_agent},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.content
    except requests.RequestException as requests_error:
        # Some long-lived crawler hosts have stale Python CA bundles while the
        # operating system trust store used by curl is still current.
        try:
            completed = subprocess.run(
                [
                    "curl", "--fail", "--silent", "--show-error", "--location",
                    "--max-time", str(max(1, timeout)), "--user-agent", user_agent, ECB_DAILY_URL,
                ],
                check=True,
                capture_output=True,
            )
            payload = completed.stdout
        except (OSError, subprocess.CalledProcessError) as curl_error:
            raise RuntimeError(
                f"ECB download failed via requests and curl: {type(requests_error).__name__}; "
                f"{type(curl_error).__name__}"
            ) from curl_error
    return parse_ecb_xml(payload)


def save_snapshot(snapshot: FxSnapshot, path: Path = FX_CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "rate_date": snapshot.rate_date,
                "source_url": snapshot.source_url,
                "rates_krw": {
                    currency: format(rate, "f")
                    for currency, rate in sorted(snapshot.rates_krw.items())
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_snapshot(path: Path = FX_CACHE_PATH) -> FxSnapshot | None:
    cache_key = str(path.resolve())
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        modified_ns = -1
    cached = _SNAPSHOT_CACHE.get(cache_key)
    if cached and cached[0] == modified_ns:
        return cached[1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rates = {
            str(currency).upper(): Decimal(str(rate))
            for currency, rate in dict(payload.get("rates_krw") or {}).items()
        }
        rate_date = str(payload.get("rate_date") or "")
    except (FileNotFoundError, OSError, ValueError, TypeError, InvalidOperation, json.JSONDecodeError):
        _SNAPSHOT_CACHE[cache_key] = (modified_ns, None)
        return None
    if not rate_date or not rates:
        _SNAPSHOT_CACHE[cache_key] = (modified_ns, None)
        return None
    rates["KRW"] = Decimal("1")
    snapshot = FxSnapshot(rate_date=rate_date, rates_krw=rates, source_url=str(payload.get("source_url") or ECB_DAILY_URL))
    _SNAPSHOT_CACHE[cache_key] = (modified_ns, snapshot)
    return snapshot


def refresh_or_cached(path: Path = FX_CACHE_PATH) -> tuple[FxSnapshot, bool, str | None]:
    try:
        snapshot = fetch_ecb_snapshot()
        save_snapshot(snapshot, path)
        return snapshot, True, None
    except Exception as error:
        cached = load_snapshot(path)
        if cached is None:
            raise RuntimeError(f"ECB 환율 갱신 실패 및 캐시 없음: {type(error).__name__}: {error}") from error
        return cached, False, f"{type(error).__name__}: {error}"


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_krw_price(value: Any) -> Decimal | None:
    text = " ".join(str(value or "").split())
    if not text or any(token in text for token in ("협의", "문의", "상담")):
        return None
    match = re.search(r"([\d,]+(?:\.\d+)?)", text)
    if not match:
        return None
    amount = Decimal(match.group(1).replace(",", ""))
    if "억" in text:
        return amount * Decimal("100000000")
    if "만원" in text:
        return amount * Decimal("10000")
    if "천원" in text:
        return amount * Decimal("1000")
    return amount


def infer_currency(price_text: Any) -> str | None:
    text = " ".join(str(price_text or "").split()).upper()
    for code in ("USD", "EUR", "GBP", "CAD", "AUD", "NZD", "JPY", "CNY", "SEK", "NOK", "DKK", "PLN", "CHF"):
        if re.search(rf"(?:^|[^A-Z]){code}(?:[^A-Z]|$)", text):
            return code
    if "€" in text:
        return "EUR"
    if "£" in text:
        return "GBP"
    if "¥" in text:
        return "JPY"
    if "$" in text:
        return "USD"
    if "원" in text:
        return "KRW"
    return None


def sale_price_fields(record: dict[str, Any], snapshot: FxSnapshot | None = None) -> dict[str, Any]:
    raw = record.get("raw")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    currency = str(record.get("sale_currency") or raw.get("currency") or "").strip().upper()
    amount = _decimal(record.get("sale_amount")) or _decimal(raw.get("native_price"))
    price_text = record.get("price")
    if not currency:
        currency = infer_currency(price_text) or ""
    if not currency and str(record.get("source_site") or "") not in INTERNATIONAL_SOURCE_NAMES:
        currency = "KRW"
    if amount is None and currency == "KRW":
        amount = parse_krw_price(price_text) or _decimal(record.get("price_krw"))

    if currency == "KRW":
        rate = Decimal("1")
        rate_date = snapshot.rate_date if snapshot else dt.date.today().isoformat()
    else:
        rate = snapshot.rates_krw.get(currency) if snapshot and currency else None
        rate_date = snapshot.rate_date if rate is not None and snapshot else None
    calculated = None
    if amount is not None and rate is not None:
        calculated = int((amount * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {
        "sale_currency": currency or None,
        "sale_amount": float(amount) if amount is not None else None,
        "sale_fx_rate_krw": float(rate) if rate is not None else None,
        "sale_fx_rate_date": rate_date,
        "price_krw": calculated,
    }
