"""Numeric summary analysis."""

from __future__ import annotations

import pandas as pd

from app.utils.validation_utils import require_columns


def summarize_numeric(df: pd.DataFrame, columns: list[str]) -> dict:
    require_columns(df, columns)
    result: dict[str, dict] = {}
    for col in columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        result[col] = {
            "count": int(numeric.count()),
            "missing": int(numeric.isna().sum()),
            "mean": round(float(numeric.mean()), 3) if numeric.count() else None,
            "median": round(float(numeric.median()), 3) if numeric.count() else None,
            "min": round(float(numeric.min()), 3) if numeric.count() else None,
            "max": round(float(numeric.max()), 3) if numeric.count() else None,
            "std": round(float(numeric.std()), 3) if numeric.count() > 1 else None,
        }
    return result
