from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline


DIRTY_MODEL_WORDS = (
    "최상급",
    "특급",
    "중급",
    "급매",
    "판매",
    "팝니다",
    "중고",
    "보링",
    "수리",
    "정비",
    "신차급",
    "무사고",
    "상태좋",
)


def normalize_model_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).upper().strip()
    text = re.sub(r"[‐‑‒–—―_/+.]+", "-", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9A-Z가-힣-]", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def compact_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).upper()
    return re.sub(r"[^0-9A-Z가-힣]", "", text)


def is_plausible_seed_model(value: Any) -> bool:
    raw = unicodedata.normalize("NFKC", str(value or "")).strip()
    normalized = normalize_model_name(raw)
    if not 2 <= len(normalized) <= 32:
        return False
    if not re.search(r"\d", normalized):
        return False
    if len(raw.split()) > 3:
        return False
    if any(word in raw for word in DIRTY_MODEL_WORDS):
        return False
    return bool(re.fullmatch(r"[0-9A-Z가-힣-]+", normalized))


def build_seed_catalog(
    rows: Iterable[dict[str, Any]],
    min_frequency: int = 10,
) -> dict[str, tuple[int, str]]:
    # Retain the public argument for callers/config compatibility. Frequency
    # no longer promotes unreviewed raw model_name values into canonical labels.
    _ = min_frequency
    normalized_counts: Counter[str] = Counter()
    for row in rows:
        model_norm = normalize_model_name(row.get("model_norm"))
        if model_norm:
            normalized_counts[model_norm] += 1

    # Canonical price-model labels must come from the crawler-curated
    # model_norm column only. Raw model_name remains resolver input, but can
    # never create a new canonical class on its own.
    return {
        model: (count, "model_norm") for model, count in normalized_counts.items()
    }


def decode_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def row_model_text(row: dict[str, Any]) -> str:
    raw = decode_json_object(row.get("raw_json"))
    detail = raw.get("detail") if isinstance(raw.get("detail"), dict) else {}
    fields = [
        row.get("model_name"),
        row.get("listing_name"),
        row.get("manufacturer"),
        detail.get("모델명"),
        detail.get("제작사"),
        detail.get("분류"),
    ]
    return " ".join(
        str(value).strip() for value in fields if value not in (None, "")
    )[:4_000]


def seed_label(row: dict[str, Any], catalog: dict[str, tuple[int, str]]) -> Optional[str]:
    model_norm = normalize_model_name(row.get("model_norm"))
    if model_norm in catalog:
        return model_norm
    return None


@dataclass(frozen=True)
class ModelResolution:
    model_name: Optional[str]
    confidence: float
    method: str


class ModelNameResolver:
    def __init__(self, catalog: dict[str, tuple[int, str]], random_seed: int = 42):
        self.catalog = dict(catalog)
        self.known_models = sorted(self.catalog, key=lambda value: (-len(compact_text(value)), value))
        self.random_seed = int(random_seed)
        self.classifier: Optional[Pipeline] = None

    def _dictionary_match(self, text: str) -> Optional[str]:
        compact = compact_text(text)
        matches: list[str] = []
        for model in self.known_models:
            compact_model = compact_text(model)
            if not compact_model:
                continue
            if len(compact_model) <= 3:
                pattern = rf"(?<![0-9A-Z가-힣]){re.escape(model)}(?![0-9A-Z가-힣])"
                if re.search(pattern, unicodedata.normalize("NFKC", text).upper()):
                    matches.append(model)
            elif compact_model in compact:
                matches.append(model)
        if not matches:
            return None
        longest = len(compact_text(matches[0]))
        equally_long = [model for model in matches if len(compact_text(model)) == longest]
        return equally_long[0] if len(equally_long) == 1 else None

    def fit(self, rows: Iterable[dict[str, Any]]) -> "ModelNameResolver":
        texts: list[str] = []
        labels: list[str] = []
        for row in rows:
            label = seed_label(row, self.catalog)
            if not label:
                continue
            base_text = row_model_text(row)
            manufacturer = str(row.get("manufacturer") or "").strip()
            # Preserve a stable training order. A set makes SGD results depend
            # on Python's per-process hash seed even with random_state fixed.
            variants = dict.fromkeys(
                (
                    base_text,
                    label,
                    f"{manufacturer} {label}".strip(),
                    f"중고 {label} 최상급",
                    f"{label} 급매",
                )
            )
            for text in variants:
                if text:
                    texts.append(text)
                    labels.append(label)
        if len(set(labels)) < 2:
            self.classifier = None
            return self
        self.classifier = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        ngram_range=(2, 5),
                        min_df=1,
                        max_features=80_000,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "classifier",
                    SGDClassifier(
                        loss="modified_huber",
                        class_weight="balanced",
                        max_iter=1500,
                        tol=1e-4,
                        random_state=self.random_seed,
                    ),
                ),
            ]
        )
        self.classifier.fit(texts, labels)
        return self

    def resolve(self, row: dict[str, Any]) -> ModelResolution:
        direct = seed_label(row, self.catalog)
        if direct:
            return ModelResolution(direct, 1.0, "seed_norm")
        text = row_model_text(row)
        dictionary_match = self._dictionary_match(text)
        if dictionary_match:
            return ModelResolution(dictionary_match, 0.98, "dictionary")
        if self.classifier is None or not text:
            return ModelResolution(None, 0.0, "unresolved")
        probabilities = np.asarray(self.classifier.predict_proba([text]))[0]
        classifier = self.classifier.named_steps["classifier"]
        index = int(np.argmax(probabilities))
        return ModelResolution(str(classifier.classes_[index]), float(probabilities[index]), "classifier")

    def save(self, path: Path) -> Path:
        output = Path(path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, output)
        output.chmod(0o600)
        return output

    @staticmethod
    def load(path: Path) -> "ModelNameResolver":
        resolver = joblib.load(Path(path).expanduser().resolve())
        if not isinstance(resolver, ModelNameResolver):
            raise TypeError("artifact is not a ModelNameResolver")
        return resolver
