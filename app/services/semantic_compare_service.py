"""Semantic comparison service: compare only the user-asked field between two spreadsheets."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.file_registry import file_registry
from app.services.comparison_exporter import export_comparison_result
from app.services.excel_service import excel_service
from app.services.key_column_detector import detect_key_column
from app.services.semantic_column_matcher import detect_target_column, extract_target_concept, profile_columns
from app.services.value_normalizer import normalize_value
from app.utils.dataframe_utils import normalize_column_name, safe_preview


class SemanticCompareService:
    def semantic_compare_excel_field(
        self,
        file_id_a: str,
        file_id_b: str,
        user_question: str,
        key_hint: str | None = None,
        field_hint: str | None = None,
        export: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Compare two files, but only for the requested target field (not full-table diff)."""

        excel_service.scan_uploads()
        meta_a = self._resolve_file(file_id_a)
        meta_b = self._resolve_file(file_id_b, exclude_file_id=meta_a.get("file_id") if meta_a else None)
        if not meta_a or not meta_b:
            return {
                "status": "error",
                "message": "Iki dosya secilemedi.",
                "data": {"file_id_a": file_id_a, "file_id_b": file_id_b, "available": excel_service.list_loaded_files()},
                "warnings": ["Iki farkli Excel/CSV dosyasi yukleyin veya file query'i netlestirin."],
                "generated_outputs": [],
            }

        df_a = file_registry.get_frame(meta_a["file_id"])
        df_b = file_registry.get_frame(meta_b["file_id"])

        concept = extract_target_concept(user_question)
        col_pick_a = detect_target_column(df_a, user_question, concept, field_hint=field_hint)
        col_pick_b = detect_target_column(df_b, user_question, concept, field_hint=field_hint)

        key_pick = detect_key_column(
            df_a,
            df_b,
            key_hint=key_hint,
            exclude_columns=[col_pick_a["selected_column"], col_pick_b["selected_column"]],
        )

        warnings: list[str] = []
        if col_pick_a["confidence"] < 0.55 or col_pick_b["confidence"] < 0.55:
            warnings.append(
                "Hedef kolon eslestirmesi belirsiz gorunuyor. Daha kesin sonuc icin field_hint ile kolon adini verin."
            )
        if key_pick["confidence"] < 0.55:
            warnings.append("Anahtar kolon tespiti belirsiz. key_hint ile satir eslestirme kolonunu belirtin (ornek: email).")

        # Decide value_type: start from concept, but if it is "text" and column profiles clearly show numeric/date/binary, upgrade.
        value_type = str(concept.get("value_type") or "text").strip().lower()
        value_type = self._refine_value_type(df_a, col_pick_a["selected_column"], value_type)

        compare = _compare_selected_field(
            df_a=df_a,
            df_b=df_b,
            key_a=key_pick["key_column_a"],
            key_b=key_pick["key_column_b"],
            field_a=col_pick_a["selected_column"],
            field_b=col_pick_b["selected_column"],
            value_type=value_type,
            preview_limit=limit,
        )

        data: dict[str, Any] = {
            "comparison_type": "semantic_field",
            "file_a": meta_a,
            "file_b": meta_b,
            "user_question": user_question,
            "target_concept": concept.get("target_concept") or concept.get("question") or "",
            "value_type": value_type,
            "key_column_a": key_pick["key_column_a"],
            "key_column_b": key_pick["key_column_b"],
            "target_column_a": col_pick_a["selected_column"],
            "target_column_b": col_pick_b["selected_column"],
            "column_confidence_a": col_pick_a["confidence"],
            "column_confidence_b": col_pick_b["confidence"],
            "key_confidence": key_pick["confidence"],
            "matched_rows": compare.get("matched_rows", 0),
            "changed_count": compare.get("changed_count", 0),
            "unchanged_count": compare.get("unchanged_count", 0),
            "only_in_a_count": compare.get("only_in_a_count", 0),
            "only_in_b_count": compare.get("only_in_b_count", 0),
            "preview_changes": compare.get("preview_changes", []),
            "only_in_a": compare.get("only_in_a", []),
            "only_in_b": compare.get("only_in_b", []),
            "warnings_context": {
                "column_detection": {"a": col_pick_a, "b": col_pick_b},
                "key_detection": key_pick,
            },
        }

        generated_outputs: list[dict[str, Any]] = []
        if export:
            export_path = export_comparison_result({"data": data})
            data["export_path"] = export_path
            generated_outputs.append(
                {
                    "type": "file",
                    "title": "semantic_field_comparison.xlsx",
                    "description": "Semantic field comparison report (Summary + Changes + OnlyInA + OnlyInB + ColumnDetection + KeyDetection).",
                    "format": "xlsx",
                    "path": export_path,
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "display": True,
                }
            )

        msg = "Hedef alanda fark bulundu." if int(data.get("changed_count") or 0) > 0 else "Hedef alanda fark bulunamadi."
        return {
            "status": "success",
            "message": msg,
            "data": data,
            "warnings": warnings,
            "generated_outputs": generated_outputs,
        }

    @staticmethod
    def _resolve_file(query: str, exclude_file_id: str | None = None) -> dict[str, Any] | None:
        q = (query or "").strip()
        if not q:
            # fallback: first loaded file
            files = excel_service.list_loaded_files()
            return files[0] if files else None

        # direct file_id
        try:
            meta = file_registry.get_meta(q)
            if exclude_file_id and meta.file_id == exclude_file_id:
                return None
            return meta.__dict__
        except Exception:
            pass

        selected = excel_service.select_file(q, category="")
        if selected and exclude_file_id and selected.get("file_id") == exclude_file_id:
            # try next best match
            matches = excel_service.find_files(q, category="")["matches"]
            alt = next((m for m in matches if m.get("file_id") != exclude_file_id), None)
            return alt
        return selected

    @staticmethod
    def _refine_value_type(df: pd.DataFrame, column: str, current: str) -> str:
        if current in {"binary", "numeric", "date"}:
            return current
        if not column or column not in df.columns:
            return current
        profs = profile_columns(df[[column]])
        if not profs:
            return current
        p = profs[0]
        if float(p["binary_like_score"]) >= 0.7:
            return "binary"
        if float(p["numeric_like_score"]) >= 0.7:
            return "numeric"
        if float(p["date_like_score"]) >= 0.7:
            return "date"
        return current


def _compare_selected_field(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    key_a: str,
    key_b: str,
    field_a: str,
    field_b: str,
    value_type: str,
    preview_limit: int = 20,
) -> dict[str, Any]:
    """Compare one field between two tables matched by detected keys."""

    if not key_a or key_a not in df_a.columns or not key_b or key_b not in df_b.columns:
        return {
            "matched_rows": 0,
            "changed_count": 0,
            "unchanged_count": 0,
            "only_in_a_count": int(len(df_a)),
            "only_in_b_count": int(len(df_b)),
            "preview_changes": [],
            "only_in_a": [],
            "only_in_b": [],
        }

    # Work on compact views.
    a = df_a[[key_a, field_a]].copy() if field_a in df_a.columns else df_a[[key_a]].copy()
    b = df_b[[key_b, field_b]].copy() if field_b in df_b.columns else df_b[[key_b]].copy()
    a.columns = ["_key", "_val_a"] if a.shape[1] == 2 else ["_key"]
    b.columns = ["_key", "_val_b"] if b.shape[1] == 2 else ["_key"]

    a["_key_norm"] = a["_key"].map(lambda v: normalize_value(v, "id"))
    b["_key_norm"] = b["_key"].map(lambda v: normalize_value(v, "id"))

    a = a[a["_key_norm"].notna() & (a["_key_norm"].astype(str).str.len() > 0)]
    b = b[b["_key_norm"].notna() & (b["_key_norm"].astype(str).str.len() > 0)]

    # Deduplicate by key (keep first) and warn via counts in output.
    dup_a = int(a["_key_norm"].duplicated().sum())
    dup_b = int(b["_key_norm"].duplicated().sum())
    a = a.drop_duplicates(subset=["_key_norm"], keep="first")
    b = b.drop_duplicates(subset=["_key_norm"], keep="first")

    merged = a.merge(b, on="_key_norm", how="outer", indicator=True)

    only_in_a = merged[merged["_merge"] == "left_only"]
    only_in_b = merged[merged["_merge"] == "right_only"]
    both = merged[merged["_merge"] == "both"].copy()

    if "_val_a" not in both.columns:
        both["_val_a"] = None
    if "_val_b" not in both.columns:
        both["_val_b"] = None

    both["_norm_a"] = both["_val_a"].map(lambda v: normalize_value(v, value_type))
    both["_norm_b"] = both["_val_b"].map(lambda v: normalize_value(v, value_type))

    changed_mask = both["_norm_a"].astype(str) != both["_norm_b"].astype(str)
    changed = both[changed_mask]
    unchanged = both[~changed_mask]

    preview_changes: list[dict[str, Any]] = []
    if len(changed):
        for _, row in changed.head(max(0, preview_limit)).iterrows():
            key_val = row["_key_norm"]
            preview_changes.append(
                {
                    "key": key_val,
                    "display_name": str(key_val) if key_val is not None else "",
                    "file_a_value": row.get("_val_a"),
                    "file_b_value": row.get("_val_b"),
                    "normalized_a": row.get("_norm_a"),
                    "normalized_b": row.get("_norm_b"),
                    "direction": f"{row.get('_val_a')} -> {row.get('_val_b')}",
                }
            )

    # Keep only minimal preview for only-in sheets.
    only_in_a_preview = safe_preview(only_in_a[["_key_norm"]].rename(columns={"_key_norm": "key"}), min(50, preview_limit))
    only_in_b_preview = safe_preview(only_in_b[["_key_norm"]].rename(columns={"_key_norm": "key"}), min(50, preview_limit))

    return {
        "matched_rows": int(len(both)),
        "changed_count": int(len(changed)),
        "unchanged_count": int(len(unchanged)),
        "only_in_a_count": int(len(only_in_a)),
        "only_in_b_count": int(len(only_in_b)),
        "preview_changes": preview_changes,
        "only_in_a": only_in_a_preview,
        "only_in_b": only_in_b_preview,
        "dedup_warnings": {"duplicate_keys_a": dup_a, "duplicate_keys_b": dup_b},
    }


semantic_compare_service = SemanticCompareService()
