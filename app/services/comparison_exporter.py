"""Export semantic comparison results into a multi-sheet Excel report."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.exporters.excel_exporter import export_multiple_sheets


def export_comparison_result(result: dict[str, Any], output_format: str = "xlsx") -> str:
    if output_format.lower() != "xlsx":
        raise ValueError("Only xlsx export is supported for now.")

    data = result.get("data") or {}

    summary_rows: list[dict[str, Any]] = []
    for key in (
        "comparison_type",
        "file_a",
        "file_b",
        "user_question",
        "value_type",
        "key_column_a",
        "key_column_b",
        "target_column_a",
        "target_column_b",
        "column_confidence_a",
        "column_confidence_b",
        "key_confidence",
        "matched_rows",
        "changed_count",
        "unchanged_count",
        "only_in_a_count",
        "only_in_b_count",
    ):
        summary_rows.append({"metric": key, "value": data.get(key)})

    df_summary = pd.DataFrame(summary_rows)

    changes = data.get("preview_changes") or []
    df_changes = pd.DataFrame(changes)

    only_a = data.get("only_in_a") or []
    df_only_a = pd.DataFrame(only_a)

    only_b = data.get("only_in_b") or []
    df_only_b = pd.DataFrame(only_b)

    ctx = data.get("warnings_context") or {}
    col_det = (ctx.get("column_detection") or {}) if isinstance(ctx, dict) else {}
    key_det = (ctx.get("key_detection") or {}) if isinstance(ctx, dict) else {}

    df_col_det = pd.DataFrame(
        [
            {
                "side": "A",
                "selected": (col_det.get("a") or {}).get("selected_column"),
                "confidence": (col_det.get("a") or {}).get("confidence"),
                "reason": (col_det.get("a") or {}).get("reason"),
            },
            {
                "side": "B",
                "selected": (col_det.get("b") or {}).get("selected_column"),
                "confidence": (col_det.get("b") or {}).get("confidence"),
                "reason": (col_det.get("b") or {}).get("reason"),
            },
        ]
    )

    df_key_det = pd.DataFrame(
        [
            {
                "key_column_a": key_det.get("key_column_a"),
                "key_column_b": key_det.get("key_column_b"),
                "confidence": key_det.get("confidence"),
                "reason": key_det.get("reason"),
                "duplicate_keys_a": key_det.get("duplicate_keys_a"),
                "duplicate_keys_b": key_det.get("duplicate_keys_b"),
                "matched_key_count": key_det.get("matched_key_count"),
                "only_in_a_count": key_det.get("only_in_a_count"),
                "only_in_b_count": key_det.get("only_in_b_count"),
            }
        ]
    )

    sheets = {
        "Summary": df_summary,
        "Changes": df_changes,
        "OnlyInA": df_only_a,
        "OnlyInB": df_only_b,
        "ColumnDetection": df_col_det,
        "KeyDetection": df_key_det,
    }

    return export_multiple_sheets(sheets, name="semantic_field_comparison")
