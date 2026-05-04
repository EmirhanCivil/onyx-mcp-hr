"""DataFrame schema and row-difference analysis."""

from __future__ import annotations

import re

import pandas as pd

from app.utils.dataframe_utils import normalize_column_name, safe_preview
from app.utils.validation_utils import require_columns


def compare_columns(df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:
    cols_a = [str(c) for c in df_a.columns]
    cols_b = [str(c) for c in df_b.columns]
    set_a = set(cols_a)
    set_b = set(cols_b)
    common = [c for c in cols_a if c in set_b]
    return {
        "columns_only_in_a": [c for c in cols_a if c not in set_b],
        "columns_only_in_b": [c for c in cols_b if c not in set_a],
        "common_columns": common,
        "same_schema": cols_a == cols_b,
        "dtype_differences": {
            col: {"a": str(df_a[col].dtype), "b": str(df_b[col].dtype)}
            for col in common
            if str(df_a[col].dtype) != str(df_b[col].dtype)
        },
    }


def row_set_difference(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    compare_columns_: list[str] | None = None,
    limit: int = 50,
) -> dict:
    columns = compare_columns_ or [c for c in df_a.columns if c in df_b.columns]
    require_columns(df_a, columns, "A dosyası kolonu")
    require_columns(df_b, columns, "B dosyası kolonu")

    a_norm = _normalized_values(df_a, columns)
    b_norm = _normalized_values(df_b, columns)
    b_keys = set(map(tuple, b_norm.to_numpy()))
    a_keys = set(map(tuple, a_norm.to_numpy()))

    only_a_mask = ~a_norm.apply(tuple, axis=1).isin(b_keys)
    only_b_mask = ~b_norm.apply(tuple, axis=1).isin(a_keys)

    only_a = df_a[only_a_mask].copy()
    only_b = df_b[only_b_mask].copy()
    only_a.insert(0, "_source_row", only_a.index.astype(int) + 2)
    only_b.insert(0, "_source_row", only_b.index.astype(int) + 2)

    return {
        "compare_columns": columns,
        "fallback_strategy": "normalized_row_fingerprint",
        "rows_only_in_a_count": int(len(only_a)),
        "rows_only_in_b_count": int(len(only_b)),
        "rows_only_in_a_preview": safe_preview(only_a, limit),
        "rows_only_in_b_preview": safe_preview(only_b, limit),
    }


def compare_by_key(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    key_columns: list[str],
    compare_columns_: list[str] | None = None,
    limit: int = 50,
) -> dict:
    require_columns(df_a, key_columns, "A dosyası anahtar kolonu")
    require_columns(df_b, key_columns, "B dosyası anahtar kolonu")
    compare_cols = compare_columns_ or [c for c in df_a.columns if c in df_b.columns and c not in key_columns]
    require_columns(df_a, compare_cols, "A dosyası karşılaştırma kolonu")
    require_columns(df_b, compare_cols, "B dosyası karşılaştırma kolonu")

    a = df_a.copy()
    b = df_b.copy()
    a["_source_row_a"] = a.index.astype(int) + 2
    b["_source_row_b"] = b.index.astype(int) + 2
    a["_join_key"] = _normalized_values(a, key_columns).agg("||".join, axis=1)
    b["_join_key"] = _normalized_values(b, key_columns).agg("||".join, axis=1)

    dup_a = int(a["_join_key"].duplicated(keep=False).sum())
    dup_b = int(b["_join_key"].duplicated(keep=False).sum())

    merged = a.merge(b, on="_join_key", how="outer", suffixes=("_a", "_b"), indicator=True)
    only_a = merged[merged["_merge"] == "left_only"]
    only_b = merged[merged["_merge"] == "right_only"]
    both = merged[merged["_merge"] == "both"]

    changed_records: list[dict] = []
    delta_view: list[dict] = []
    changed_column_counts: dict[str, int] = {}
    for _, row in both.iterrows():
        changes = {}
        for col in compare_cols:
            left = row.get(f"{col}_a")
            right = row.get(f"{col}_b")
            left_norm = _normalize_compare_value(left)
            right_norm = _normalize_compare_value(right)
            if left_norm != right_norm:
                changes[col] = {"a": None if pd.isna(left) else left, "b": None if pd.isna(right) else right}
                changed_column_counts[col] = changed_column_counts.get(col, 0) + 1
                if len(delta_view) < max(limit * 3, 50):
                    key_payload = {key: row.get(f"{key}_a", row.get(f"{key}_b")) for key in key_columns}
                    delta_view.append(
                        {
                            **key_payload,
                            "column": col,
                            "old_value": None if pd.isna(left) else left,
                            "new_value": None if pd.isna(right) else right,
                            "source_row_a": row.get("_source_row_a"),
                            "source_row_b": row.get("_source_row_b"),
                        }
                    )
        if changes:
            record = {key: row.get(f"{key}_a", row.get(f"{key}_b")) for key in key_columns}
            record["source_row_a"] = row.get("_source_row_a")
            record["source_row_b"] = row.get("_source_row_b")
            record["changed_columns"] = changes
            changed_records.append(record)

    changed_columns_ranked = sorted(
        [{"column": col, "changed_count": int(count)} for col, count in changed_column_counts.items()],
        key=lambda x: x["changed_count"],
        reverse=True,
    )

    return {
        "key_columns": key_columns,
        "compared_columns": compare_cols,
        "matched_keys": int(len(both)),
        "only_in_a_count": int(len(only_a)),
        "only_in_b_count": int(len(only_b)),
        "changed_row_count": int(len(changed_records)),
        "changed_rows_preview": changed_records[:limit],
        "delta_view_preview": delta_view[: max(limit * 3, limit)],
        "changed_columns_ranked": changed_columns_ranked[: min(len(changed_columns_ranked), 50)],
        "key_duplicate_rows": {"a": dup_a, "b": dup_b},
        "only_in_a_preview": safe_preview(only_a.drop(columns=["_join_key", "_merge"], errors="ignore"), limit),
        "only_in_b_preview": safe_preview(only_b.drop(columns=["_join_key", "_merge"], errors="ignore"), limit),
    }


def _normalized_values(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df[columns].copy()
    for col in out.columns:
        out[col] = out[col].map(_normalize_compare_value)
    return out


def _normalize_compare_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _format_number(float(value))

    text = str(value).strip()
    if not text:
        return ""

    if _looks_like_date(text):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
        if not pd.isna(parsed):
            return parsed.date().isoformat()

    normalized_number = _normalize_number_text(text)
    if normalized_number is not None:
        return normalized_number

    return normalize_column_name(text)


def _looks_like_date(text: str) -> bool:
    if not re.search(r"\d", text):
        return False
    return bool(re.search(r"\d{1,4}[-./]\d{1,2}[-./]\d{1,4}", text))


def _normalize_number_text(text: str) -> str | None:
    compact = text.replace(" ", "")
    if not re.fullmatch(r"[-+]?\d+([.,]\d+)?%?", compact):
        return None
    numeric_text = compact.rstrip("%").replace(",", ".")
    integer_part = numeric_text.lstrip("+-").split(".", 1)[0]
    if len(integer_part) > 1 and integer_part.startswith("0") and "." not in numeric_text:
        return None
    try:
        return _format_number(float(numeric_text))
    except ValueError:
        return None


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.10f}".rstrip("0").rstrip(".")
