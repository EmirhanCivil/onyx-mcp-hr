"""Heuristics for identifying spreadsheet and survey column roles."""

from __future__ import annotations

import pandas as pd

from app.config import settings
from app.utils.dataframe_utils import normalize_column_name


GROUP_HINTS = {
    "birim", "departman", "department", "directorate", "division", "unit", "ekip", "team",
    "lokasyon", "location", "sehir", "city", "bolge", "region", "rol", "role", "unvan",
    "title", "kategori", "category", "segment", "tip", "type", "sube", "branch",
}
SCORE_HINTS = {
    "skor", "score", "puan", "rating", "memnuniyet", "satisfaction", "baglilik",
    "engagement", "performans", "performance", "kalite", "quality", "egitim", "training",
    "iletisim", "communication", "yonetici", "manager", "kariyer", "career", "is yuku",
    "workload", "nps", "ces", "csat",
}
COMMENT_HINTS = {
    "yorum", "comment", "gorus", "feedback", "oner", "suggestion", "sikayet",
    "complaint", "aciklama", "description", "not", "note", "reason", "sebep",
}
CATEGORY_HINTS = {
    "durum", "status", "state", "oncelik", "priority", "kategori", "category",
    "tip", "type", "sinif", "class", "sonuc", "result", "karar", "decision",
}
TIME_HINTS = {
    "tarih", "date", "created", "updated", "donem", "period", "ay", "month",
    "yil", "year", "hafta", "week", "quarter", "ceyrek",
}
KEY_HINTS = {
    "id", "record id", "unique id", "employee id", "candidate id", "customer id",
    "product id", "order id", "transaction id", "invoice id", "ticket id", "asset id",
    "sicil", "personel no", "email", "mail", "sku", "stok kodu", "urun kodu",
    "plaka", "license plate", "vin", "serial no", "seri no", "barcode", "barkod",
}


def detect_columns(df: pd.DataFrame) -> dict:
    columns = [str(c) for c in df.columns]
    normalized = {str(c): normalize_column_name(c) for c in df.columns}

    numeric_columns = [col for col in columns if _numeric_ratio(df[col]) >= 0.8]
    date_columns = [col for col in columns if _looks_like_date(df[col], normalized[col])]
    comment_columns = [
        col for col in columns
        if col not in numeric_columns and _looks_like_comment(df[col], normalized[col])
    ]
    group_columns = [
        col for col in columns
        if col not in comment_columns and _looks_like_group(df[col], normalized[col])
    ]
    likely_score_columns = [
        col for col in numeric_columns
        if _looks_like_score(df[col], normalized[col])
    ]
    categorical_columns = [
        col for col in columns
        if col not in comment_columns and col not in likely_score_columns and _looks_like_category(df[col], normalized[col])
    ]
    key_candidates = _key_candidates(df, normalized, set(comment_columns))
    key_columns = [item["column"] for item in key_candidates]

    return {
        "all_columns": columns,
        "group_columns": group_columns,
        "numeric_columns": numeric_columns,
        "likely_score_columns": likely_score_columns,
        "comment_columns": comment_columns,
        "categorical_columns": categorical_columns,
        "date_columns": date_columns,
        "time_columns": date_columns,
        "key_columns": key_columns,
        "key_candidates": key_candidates,
        "score_scales": {col: _score_scale(df[col]) for col in likely_score_columns},
        "role_map": {
            "group": group_columns,
            "score": likely_score_columns,
            "comment": comment_columns,
            "category": categorical_columns,
            "key": key_columns,
            "time": date_columns,
        },
    }


def _looks_like_score(series: pd.Series, normalized_name: str = "") -> bool:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return False
    in_scale = values.between(0, 10).mean() >= 0.9
    enough_numeric = _numeric_ratio(series) >= 0.8
    if not in_scale or not enough_numeric:
        return False
    if any(_hint_matches(normalized_name, token) for token in SCORE_HINTS):
        return True
    return values.nunique(dropna=True) <= 11 and len(values) >= 3


def _looks_like_comment(series: pd.Series, normalized_name: str) -> bool:
    if any(_hint_matches(normalized_name, token) for token in COMMENT_HINTS):
        return True
    sample = series.dropna().astype(str).head(100)
    if sample.empty:
        return False
    avg_len = sample.map(len).mean()
    unique_rate = sample.nunique() / max(len(sample), 1)
    return bool(avg_len >= 30 and unique_rate >= 0.5)


def _looks_like_group(series: pd.Series, normalized_name: str) -> bool:
    if any(_hint_matches(normalized_name, token) for token in GROUP_HINTS):
        return True
    sample = series.dropna().astype(str).head(500)
    if sample.empty:
        return False
    unique_count = sample.nunique(dropna=True)
    unique_rate = unique_count / max(len(sample), 1)
    return bool(2 <= unique_count <= 50 and unique_rate <= 0.5)


def _looks_like_category(series: pd.Series, normalized_name: str) -> bool:
    if any(_hint_matches(normalized_name, token) for token in CATEGORY_HINTS):
        return True
    sample = series.dropna().astype(str).head(500)
    if sample.empty:
        return False
    unique_count = sample.nunique(dropna=True)
    unique_rate = unique_count / max(len(sample), 1)
    return bool(2 <= unique_count <= 30 and unique_rate <= 0.35)


def _looks_like_date(series: pd.Series, normalized_name: str) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not any(_hint_matches(normalized_name, token) for token in TIME_HINTS):
        return False
    sample = series.dropna().head(200)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", dayfirst=True)
    return bool(parsed.notna().mean() >= 0.7)


def _key_candidates(df: pd.DataFrame, normalized: dict[str, str], excluded_columns: set[str]) -> list[dict]:
    candidates = []
    for col in df.columns:
        name = str(col)
        if name in excluded_columns:
            continue
        norm = normalized[name]
        series = df[col]
        non_null = float(series.notna().mean()) if len(series) else 0.0
        unique_rate = float(series.dropna().nunique() / max(len(series), 1))
        name_signal = any(_hint_matches(norm, normalize_column_name(hint)) for hint in KEY_HINTS)
        avg_len = float(series.dropna().astype(str).head(200).map(len).mean()) if series.notna().any() else 0.0
        if not name_signal and unique_rate < 0.9:
            continue
        if not name_signal and avg_len >= 40:
            continue
        score = (unique_rate * 0.55) + (non_null * 0.25) + (0.2 if name_signal else 0)
        if score >= 0.75:
            candidates.append({
                "column": name,
                "confidence": round(score, 3),
                "unique_rate": round(unique_rate, 3),
                "non_null_rate": round(non_null, 3),
                "name_signal": name_signal,
            })
    return sorted(candidates, key=lambda item: item["confidence"], reverse=True)[:5]


def _numeric_ratio(series: pd.Series) -> float:
    sample = series.dropna().head(500)
    if sample.empty:
        return 0.0
    return float(pd.to_numeric(sample, errors="coerce").notna().mean())


def _score_scale(series: pd.Series) -> dict:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"min": None, "max": None, "likely_scale": ""}
    max_value = float(values.max())
    likely_scale = "1-5" if max_value <= 5 else "1-10"
    return {"min": float(values.min()), "max": max_value, "likely_scale": likely_scale}


def _hint_matches(norm: str, hint_norm: str) -> bool:
    if not hint_norm:
        return False
    if " " in hint_norm:
        return hint_norm in norm
    tokens = set(norm.split())
    if hint_norm in tokens or hint_norm == norm:
        return True
    return len(hint_norm) > 4 and hint_norm in norm
