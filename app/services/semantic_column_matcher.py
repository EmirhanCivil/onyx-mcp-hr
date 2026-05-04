"""Semantic column profiling and target-column detection for spreadsheet comparison.

Goal: user asks about a specific concept/field (binary/numeric/date/text) and we
find the most relevant column without hardcoding a domain (HR, products, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from app.services.value_normalizer import normalize_value
from app.utils.dataframe_utils import normalize_column_name


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_STOPWORDS = {
    # TR
    "mi",
    "mu",
    "mı",
    "mü",
    "var",
    "yok",
    "kac",
    "kaç",
    "tane",
    "adet",
    "olan",
    "olmayan",
    "ile",
    "ve",
    "ya",
    "yada",
    "arasında",
    "arasinda",
    "fark",
    "farki",
    "farkı",
    "degis",
    "degisti",
    "degismis",
    "değiş",
    "değişti",
    "değişmiş",
    "karsilastir",
    "kıyasla",
    "kıyas",
    "karsilastirma",
    "karsilastirir",
    "kıyaslar",
    "sadece",
    "alan",
    "kolon",
    "sutun",
    "sütun",
    "hucre",
    "hücre",
    # EN
    "compare",
    "difference",
    "diff",
    "changed",
    "change",
    "between",
    "only",
    "field",
    "column",
}

_SYNONYMS: dict[str, set[str]] = {
    # Keep small and generic; not domain-locked.
    "durum": {"status", "state", "stage"},
    "status": {"durum", "stage"},
    "fiyat": {"price", "amount", "cost", "charge"},
    "price": {"fiyat", "tutar", "ucret"},
    "tutar": {"amount", "total", "sum", "price", "cost"},
    "tarih": {"date", "created", "updated", "time"},
    "date": {"tarih", "created", "updated"},
    "puan": {"score", "rating", "skor"},
    "skor": {"score", "rating", "puan"},
    "form": {"form", "submit", "submission"},
    "aktif": {"active", "enabled"},
    "pasif": {"inactive", "disabled"},
    "mail": {"email", "e posta", "eposta"},
    "email": {"mail", "e posta", "eposta"},
    "telefon": {"phone", "gsm", "mobile"},
    "phone": {"telefon", "gsm", "mobile"},
}


@dataclass(frozen=True)
class TargetConcept:
    question: str
    normalized_question: str
    keywords: list[str]
    value_type: str  # binary|numeric|date|text


@dataclass(frozen=True)
class ColumnPick:
    selected_column: str
    confidence: float
    reason: str
    alternatives: list[dict[str, Any]]
    value_type: str


def extract_target_concept(user_question: str) -> dict[str, Any]:
    """Extract a lightweight concept description from the user question.

    We keep this intentionally heuristic and domain-agnostic.
    """

    q_raw = (user_question or "").strip()
    q_norm = normalize_column_name(q_raw)

    base_tokens = [tok for tok in q_norm.split() if tok and tok not in _STOPWORDS and not tok.isdigit()]
    expanded: list[str] = []
    seen = set()
    for tok in base_tokens:
        if tok in seen:
            continue
        seen.add(tok)
        expanded.append(tok)
        for syn in sorted(_SYNONYMS.get(tok, set())):
            syn_n = normalize_column_name(syn)
            if syn_n and syn_n not in seen:
                seen.add(syn_n)
                expanded.append(syn_n)
    tokens = expanded

    # Value-type intent heuristics (keep generic).
    binary_markers = {
        "var",
        "yok",
        "aktif",
        "pasif",
        "enabled",
        "disabled",
        "true",
        "false",
        "iletildi",
        "iletilmedi",
        "gonderildi",
        "gonderilmedi",
        "sent",
        "delivered",
        "undelivered",
    }
    numeric_markers = {"fiyat", "tutar", "ucret", "ücret", "amount", "price", "score", "puan", "skor", "rating", "nps", "csat", "ces", "maas", "maaş"}
    date_markers = {"tarih", "date", "created", "updated", "gun", "gün", "ay", "yil", "yıl", "donem", "dönem"}

    value_type = "text"
    if any(tok in q_norm for tok in binary_markers):
        value_type = "binary"
    elif any(tok in q_norm for tok in numeric_markers):
        value_type = "numeric"
    elif any(tok in q_norm for tok in date_markers):
        value_type = "date"

    concept = TargetConcept(
        question=q_raw,
        normalized_question=q_norm,
        keywords=tokens[:24],
        value_type=value_type,
    )
    return {
        "target_concept": " ".join(concept.keywords[:6]) if concept.keywords else concept.question,
        "question": concept.question,
        "normalized_question": concept.normalized_question,
        "keywords": concept.keywords,
        "value_type": concept.value_type,
        "intent": "field_diff",
    }


def profile_columns(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Profile each column by both name and contents (crucial for robust matching)."""

    rows = int(len(df))
    profiles: list[dict[str, Any]] = []

    for col in df.columns:
        col_name = str(col)
        norm_name = normalize_column_name(col_name)
        s = df[col]
        non_null = s.dropna()
        non_null_ratio = float(len(non_null) / max(rows, 1))
        unique_count = int(non_null.nunique(dropna=True))
        unique_ratio = float(unique_count / max(int(len(non_null)), 1))

        sample_values: list[str] = []
        if len(non_null):
            try:
                vc = non_null.astype(str).value_counts(dropna=True)
                sample_values = [str(v) for v in list(vc.index[:5])]
            except Exception:
                sample_values = [str(v) for v in list(non_null.astype(str).unique()[:5])]

        dtype = "text"
        if pd.api.types.is_numeric_dtype(s.dtype):
            dtype = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s.dtype):
            dtype = "date"

        # Content-based "likeness" scores (0-1).
        sample = non_null
        if len(sample) > 500:
            sample = sample.sample(n=500, random_state=7)

        binary_like = _binary_like_score(sample)
        numeric_like = _numeric_like_score(sample)
        date_like = _date_like_score(sample)
        email_like = _email_like_score(sample)
        id_like = _id_like_score(sample, unique_ratio, norm_name)
        key_like = max(email_like, id_like)

        profiles.append(
            {
                "column_name": col_name,
                "normalized_name": norm_name,
                "dtype": dtype,
                "non_null_ratio": round(non_null_ratio, 4),
                "unique_count": unique_count,
                "unique_ratio": round(unique_ratio, 6),
                "sample_values": sample_values,
                "binary_like_score": round(binary_like, 4),
                "numeric_like_score": round(numeric_like, 4),
                "date_like_score": round(date_like, 4),
                "email_like_score": round(email_like, 4),
                "id_like_score": round(id_like, 4),
                "key_like_score": round(float(key_like), 4),
            }
        )

    return profiles


def detect_target_column(
    df: pd.DataFrame,
    user_question: str,
    target_concept: dict[str, Any],
    field_hint: str | None = None,
) -> dict[str, Any]:
    """Pick the best matching column for the question/concept.

    Scoring is intentionally simple and explainable (no heavy embeddings).
    """

    q_norm = normalize_column_name(user_question)
    concept_keywords = [normalize_column_name(k) for k in (target_concept.get("keywords") or []) if k]
    value_type = str(target_concept.get("value_type") or "text").strip().lower()

    profiles = profile_columns(df)
    best = ("", -1.0, "")
    alternatives: list[tuple[str, float]] = []

    for prof in profiles:
        col_name = prof["column_name"]
        col_norm = prof["normalized_name"]
        score = 0.0
        reasons: list[str] = []

        if field_hint:
            hint_norm = normalize_column_name(field_hint)
            name_sim = _sim(hint_norm, col_norm)
            if name_sim >= 0.75:
                score += 80.0
                reasons.append("field_hint match")

        # Column name ~ question match.
        name_q_sim = _sim(q_norm, col_norm)
        if name_q_sim > 0:
            score += 40.0 * name_q_sim

        # Column name ~ concept keywords match.
        if concept_keywords:
            kw_best = max((_sim(kw, col_norm) for kw in concept_keywords), default=0.0)
            score += 30.0 * kw_best

        # Content-type fit.
        if value_type == "binary":
            score += 30.0 * float(prof["binary_like_score"])
        elif value_type == "numeric":
            score += 30.0 * float(prof["numeric_like_score"])
        elif value_type == "date":
            score += 30.0 * float(prof["date_like_score"])

        # Penalize too-empty columns.
        if float(prof["non_null_ratio"]) < 0.2:
            score -= 20.0

        # Light penalty if data type is clearly mismatched.
        if value_type == "numeric" and float(prof["numeric_like_score"]) < 0.2 and prof["dtype"] == "text":
            score -= 10.0
        if value_type == "date" and float(prof["date_like_score"]) < 0.2:
            score -= 10.0

        alternatives.append((col_name, float(score)))
        if score > best[1]:
            best = (col_name, float(score), "; ".join(reasons) if reasons else "name/content similarity")

    alternatives_sorted = sorted(alternatives, key=lambda x: x[1], reverse=True)
    selected, raw_score, reason = best

    # Map score to 0-1 confidence.
    conf = max(0.0, min(1.0, raw_score / 100.0))

    alt_payload = [{"column": name, "confidence": round(max(0.0, min(1.0, sc / 100.0)), 4)} for name, sc in alternatives_sorted[1:4]]

    # If user intent says binary/numeric/date but column profile strongly contradicts,
    # downgrade a bit.
    selected_prof = next((p for p in profiles if p["column_name"] == selected), None)
    if selected_prof:
        if value_type == "binary" and float(selected_prof["binary_like_score"]) < 0.2:
            conf = max(0.0, conf - 0.15)
        if value_type == "numeric" and float(selected_prof["numeric_like_score"]) < 0.2:
            conf = max(0.0, conf - 0.15)
        if value_type == "date" and float(selected_prof["date_like_score"]) < 0.2:
            conf = max(0.0, conf - 0.15)

    return ColumnPick(
        selected_column=selected,
        confidence=round(conf, 4),
        reason=reason or "best match",
        alternatives=alt_payload,
        value_type=value_type,
    ).__dict__


def _sim(a: str, b: str) -> float:
    a = normalize_column_name(a)
    b = normalize_column_name(b)
    if not a or not b:
        return 0.0
    return float(SequenceMatcher(a=a, b=b).ratio())


def _binary_like_score(sample: pd.Series) -> float:
    if sample is None or len(sample) == 0:
        return 0.0
    uniques = pd.Series(sample.astype(str).unique()[:20]).dropna()
    if len(uniques) == 0:
        return 0.0
    if len(uniques) > 6:
        return 0.0
    mapped = [normalize_value(v, "binary") for v in uniques]
    mapped_non_null = [m for m in mapped if m is not None]
    if not mapped_non_null:
        return 0.0
    coverage = len(mapped_non_null) / max(len(mapped), 1)
    has_true = any(m is True for m in mapped_non_null)
    has_false = any(m is False for m in mapped_non_null)
    diversity = 1.0 if (has_true and has_false) else 0.7
    return float(min(1.0, coverage * diversity))


def _numeric_like_score(sample: pd.Series) -> float:
    if sample is None or len(sample) == 0:
        return 0.0
    if pd.api.types.is_numeric_dtype(sample.dtype):
        return 1.0
    txt = sample.astype(str).map(lambda x: x.strip()).replace("", pd.NA).dropna()
    if len(txt) == 0:
        return 0.0
    parsed = txt.map(lambda x: normalize_value(x, "numeric"))
    ok = parsed.map(lambda x: x is not None).sum()
    return float(ok / max(len(parsed), 1))


def _date_like_score(sample: pd.Series) -> float:
    if sample is None or len(sample) == 0:
        return 0.0
    if pd.api.types.is_datetime64_any_dtype(sample.dtype):
        return 1.0
    txt = sample.astype(str).map(lambda x: x.strip()).replace("", pd.NA).dropna()
    if len(txt) == 0:
        return 0.0
    parsed = pd.to_datetime(txt, errors="coerce", dayfirst=True)
    ok = int(parsed.notna().sum())
    return float(ok / max(len(parsed), 1))


def _email_like_score(sample: pd.Series) -> float:
    if sample is None or len(sample) == 0:
        return 0.0
    txt = sample.astype(str).map(lambda x: x.strip()).replace("", pd.NA).dropna()
    if len(txt) == 0:
        return 0.0
    ok = int(txt.map(lambda x: bool(_EMAIL_RE.match(x))).sum())
    return float(ok / max(len(txt), 1))


def _id_like_score(sample: pd.Series, unique_ratio: float, norm_col_name: str) -> float:
    if sample is None or len(sample) == 0:
        return 0.0

    name_bonus = 0.0
    if any(tok in norm_col_name for tok in ("id", "no", "kod", "code", "key", "uuid", "sicil")):
        name_bonus = 0.25

    txt = sample.astype(str).map(lambda x: x.strip()).replace("", pd.NA).dropna()
    if len(txt) == 0:
        return 0.0

    # "ID-like": mostly unique + alnum tokens with digits.
    def looks_id(v: str) -> bool:
        v2 = normalize_column_name(v)
        if len(v2) < 3:
            return False
        has_digit = any(ch.isdigit() for ch in v2)
        alpha = any(ch.isalpha() for ch in v2)
        return has_digit and (alpha or v2.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")))

    ok = int(txt.map(looks_id).sum())
    coverage = ok / max(len(txt), 1)
    uniq = float(unique_ratio)
    score = 0.55 * min(1.0, uniq) + 0.45 * coverage + name_bonus
    return float(min(1.0, score))
