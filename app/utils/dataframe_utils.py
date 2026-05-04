"""DataFrame helpers for summaries, previews, and normalization."""

from __future__ import annotations

import unicodedata

import pandas as pd

from app.config import settings


def normalize_column_name(name: object) -> str:
    text = str(name).strip().lower().replace("_", " ").replace("-", " ").replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    # Turkish dotless i tolerance ("IK" vs "İK" vs "ık").
    text = text.replace("ı", "i")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())


def normalize_row_values(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    cols = columns or list(df.columns)
    normalized = df[cols].copy()
    for col in normalized.columns:
        normalized[col] = normalized[col].map(lambda x: "" if pd.isna(x) else str(x).strip())
    return normalized


def dataframe_profile(df: pd.DataFrame) -> dict:
    numeric_cols = [str(c) for c in df.select_dtypes(include="number").columns]
    date_cols = [str(c) for c in df.select_dtypes(include=["datetime", "datetimetz"]).columns]
    text_cols = [str(c) for c in df.columns if c not in numeric_cols and c not in date_cols]
    missing = df.isna().sum()
    missing_rates = (missing / max(len(df), 1) * 100).round(2)

    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "column_count": int(len(df.columns)),
        "numeric_columns": numeric_cols,
        "text_columns": text_cols,
        "date_columns": date_cols,
        "missing_values": {str(k): int(v) for k, v in missing.items()},
        "missing_rates_percent": {str(k): float(v) for k, v in missing_rates.items()},
        "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
        "memory_mb": round(float(df.memory_usage(deep=True).sum()) / (1024 * 1024), 2),
        "is_large_file": bool(len(df) >= settings.LARGE_FILE_ROW_THRESHOLD),
    }


def safe_preview(df: pd.DataFrame, limit: int | None = None) -> list[dict]:
    max_rows = min(limit or settings.MAX_PREVIEW_ROWS, settings.MAX_PREVIEW_ROWS)
    preview = df.head(max_rows).copy()
    return preview.where(pd.notna(preview), None).to_dict(orient="records")


def column_values_as_strings(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df[columns].copy()
    for col in out.columns:
        out[col] = out[col].map(lambda value: "" if pd.isna(value) else str(value).strip())
    return out
