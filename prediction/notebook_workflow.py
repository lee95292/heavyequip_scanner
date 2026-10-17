from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from prediction.cleaning import build_clean_candidate
from prediction.config import PredictionSettings
from prediction.model_name import ModelNameResolver, build_seed_catalog


@dataclass(frozen=True)
class InMemoryCleaningResult:
    raw_frame: pd.DataFrame
    cleaned_frame: pd.DataFrame
    audit_frame: pd.DataFrame
    catalog_frame: pd.DataFrame


def records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    normalized = frame.astype(object).where(pd.notna(frame), None)
    records = normalized.to_dict(orient="records")
    for index, row in enumerate(records, 1):
        row["source_listing_id"] = int(row.get("source_listing_id") or index)
    return records


def _fallback_record_key(row: dict[str, Any]) -> str:
    identity = {
        key: row.get(key)
        for key in (
            "source_site",
            "pid",
            "detail_url",
            "posted_at",
            "listing_name",
            "model_name",
            "price",
            "contact",
        )
    }
    payload = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_local_parsed_records(directory: Path) -> list[dict[str, Any]]:
    source_dir = Path(directory).expanduser().resolve()
    unique: dict[str, dict[str, Any]] = {}
    for path in sorted(source_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for value in payload:
            if not isinstance(value, dict):
                continue
            row = dict(value)
            row["raw_json"] = row.get("raw_json") or row.get("raw")
            key = str(row.get("content_hash") or _fallback_record_key(row))
            unique[key] = row

    records: list[dict[str, Any]] = []
    for source_listing_id, (_, row) in enumerate(sorted(unique.items()), 1):
        records.append({**row, "source_listing_id": source_listing_id})
    return records


def clean_records_in_memory(
    records: Iterable[dict[str, Any]],
    settings: PredictionSettings,
) -> InMemoryCleaningResult:
    rows = sorted(
        (dict(row) for row in records),
        key=lambda row: int(row.get("source_listing_id") or 0),
    )
    catalog = build_seed_catalog(rows, settings.min_model_frequency)
    resolver = ModelNameResolver(catalog, settings.random_seed).fit(rows)
    seller_keys: set[str] = set()
    contact_keys: set[str] = set()
    cleaned_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    for raw_row in rows:
        source_id = int(raw_row["source_listing_id"])
        try:
            resolution = resolver.resolve(raw_row)
            candidate = build_clean_candidate(raw_row, resolution, settings)
        except (TypeError, ValueError, OverflowError) as error:
            audit_rows.append(
                {
                    "source_listing_id": source_id,
                    "status": "rejected",
                    "method": "normalization_error",
                    "confidence": 0.0,
                    "source_site": raw_row.get("source_site"),
                    "category_name": raw_row.get("category_name"),
                    "message": type(error).__name__,
                }
            )
            continue

        status = candidate.status
        if candidate.row is not None:
            seller_key = candidate.row.get("seller_dedupe_hash")
            contact_key = candidate.row.get("contact_dedupe_hash")
            duplicate = bool(
                (seller_key and seller_key in seller_keys)
                or (contact_key and contact_key in contact_keys)
            )
            if duplicate:
                status = "duplicate"
            else:
                if seller_key:
                    seller_keys.add(str(seller_key))
                if contact_key:
                    contact_keys.add(str(contact_key))
                cleaned_rows.append(candidate.row)

        audit_rows.append(
            {
                "source_listing_id": source_id,
                "status": status,
                "method": resolution.method,
                "confidence": float(resolution.confidence),
                "source_site": raw_row.get("source_site"),
                "category_name": raw_row.get("category_name"),
                "message": candidate.message,
            }
        )

    catalog_rows = [
        {
            "model_norm": model,
            "observation_count": count,
            "seed_source": source,
        }
        for model, (count, source) in sorted(catalog.items())
    ]
    return InMemoryCleaningResult(
        raw_frame=pd.DataFrame(rows),
        cleaned_frame=pd.DataFrame(cleaned_rows),
        audit_frame=pd.DataFrame(audit_rows),
        catalog_frame=pd.DataFrame(catalog_rows),
    )
