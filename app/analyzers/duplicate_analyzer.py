"""Duplicate detection and de-duplication helpers."""

from __future__ import annotations

import pandas as pd

from app.utils.dataframe_utils import column_values_as_strings
from app.utils.validation_utils import require_columns


def find_duplicates(df: pd.DataFrame, key_columns: list[str] | None = None, keep: str = "first") -> dict:
    columns = key_columns or list(df.columns)
    require_columns(df, columns)
    normalized = column_values_as_strings(df, columns)
    mask = normalized.duplicated(keep=False)
    duplicate_groups = normalized[mask].value_counts().reset_index(name="count")
    duplicate_rows = df[mask].copy()
    duplicate_rows.insert(0, "_source_row", duplicate_rows.index.astype(int) + 2)

    return {
        "key_columns": columns,
        "duplicate_group_count": int(len(duplicate_groups)),
        "duplicate_row_count": int(mask.sum()),
        "unique_after_dedup": int(len(df.drop_duplicates(subset=columns, keep=keep))),
        "groups_preview": duplicate_groups.head(50).to_dict(orient="records"),
        "rows_preview": duplicate_rows.head(50).where(pd.notna(duplicate_rows), None).to_dict(orient="records"),
    }


def deduplicate(df: pd.DataFrame, key_columns: list[str] | None = None, keep: str = "first") -> tuple[pd.DataFrame, dict]:
    columns = key_columns or list(df.columns)
    require_columns(df, columns)
    before = len(df)
    cleaned = df.drop_duplicates(subset=columns, keep=keep).copy()
    summary = {
        "key_columns": columns,
        "keep": keep,
        "rows_before": int(before),
        "rows_after": int(len(cleaned)),
        "removed_rows": int(before - len(cleaned)),
    }
    return cleaned, summary
