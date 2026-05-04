"""Candidate stage transition analysis between two spreadsheet periods."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.exporters.excel_exporter import export_multiple_sheets
from app.services.excel_compare_service import excel_compare_service
from app.services.excel_service import excel_service
from app.services.hr_column_normalization_service import hr_column_normalization_service
from app.utils.dataframe_utils import normalize_column_name, safe_preview


class HRTransitionsService:
    def analyze(
        self,
        file_query_a: str = "",
        file_query_b: str = "",
        file_id_a: str = "",
        file_id_b: str = "",
        key_query: str = "email telefon candidate id aday id",
        export: bool = True,
        limit: int = 50,
    ) -> dict:
        excel_service.scan_uploads()

        a = {"file_id": file_id_a} if file_id_a else excel_service.select_file(file_query_a, "excel")
        b = {"file_id": file_id_b} if file_id_b else excel_service.select_file(file_query_b, "excel")
        if not a or not a.get("file_id") or not b or not b.get("file_id"):
            raise InvalidInputError("Iki donem icin iki Excel secilemedi. file_query_a/file_query_b verin.")

        file_id_a = a["file_id"]
        file_id_b = b["file_id"]

        # Use auto compare to infer key columns and align semantic columns.
        compare = excel_compare_service.compare_auto(file_id_a, file_id_b, key_query=key_query, limit=20, export=False)
        inferred_keys = compare.get("inferred_key_columns") or []
        mapped_columns = [item["a"] for item in compare.get("mapped_columns", [])] if compare.get("mapped_columns") else []

        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)

        # Stage column detection on each side (use normalization on original DFs).
        norm_a = hr_column_normalization_service.normalize(df_a)
        norm_b = hr_column_normalization_service.normalize(df_b)
        stage_a = norm_a.get("canonical_mapping", {}).get("status", "")
        stage_b = norm_b.get("canonical_mapping", {}).get("status", "")
        if not stage_a or not stage_b:
            raise InvalidInputError("Surec/durum kolonu bulunamadi. Kolon adlarini netlestirin veya dosya tipini kontrol edin.")

        # Key selection
        keys = [k for k in inferred_keys if k in df_a.columns and k in df_b.columns]
        if not keys:
            # fall back to best common identifier
            fallback_keys = []
            for cand in (norm_a.get("canonical_mapping", {}).get("email"), norm_a.get("canonical_mapping", {}).get("phone")):
                if cand and cand in df_a.columns and cand in df_b.columns:
                    fallback_keys.append(cand)
            keys = fallback_keys[:1]
        if not keys:
            raise InvalidInputError("Anahtar kolon bulunamadi. Email/telefon/id gibi anahtarlar olmadan gecis analizi guvenilmez.")

        # Build join key
        def join_key(df: pd.DataFrame) -> pd.Series:
            parts = []
            for k in keys:
                parts.append(df[k].map(lambda v: normalize_column_name("" if pd.isna(v) else v)))
            if len(parts) == 1:
                return parts[0]
            out = parts[0]
            for p in parts[1:]:
                out = out + "||" + p
            return out

        a_work = df_a.copy()
        b_work = df_b.copy()
        a_work["_k"] = join_key(a_work)
        b_work["_k"] = join_key(b_work)

        # Normalize statuses
        a_work["_stage"] = a_work[stage_a].map(lambda v: hr_column_normalization_service.normalize_status(v)["normalized"])
        b_work["_stage"] = b_work[stage_b].map(lambda v: hr_column_normalization_service.normalize_status(v)["normalized"])

        merged = a_work[["_k", "_stage"] + keys].merge(b_work[["_k", "_stage"] + keys], on="_k", how="outer", suffixes=("_a", "_b"), indicator=True)

        new_rows = merged[merged["_merge"] == "right_only"].copy()
        dropped_rows = merged[merged["_merge"] == "left_only"].copy()
        common = merged[merged["_merge"] == "both"].copy()

        common["from_stage"] = common["_stage_a"]
        common["to_stage"] = common["_stage_b"]
        transitions = common.groupby(["from_stage", "to_stage"]).size().reset_index(name="count").sort_values("count", ascending=False)

        # Movement classification
        progressed = common[common["from_stage"] != common["to_stage"]].copy()
        stayed = common[common["from_stage"] == common["to_stage"]].copy()

        # Bottleneck: biggest "waiting/form_waiting/technical_interview/hr_interview" stable or inflow
        bottleneck = None
        if not transitions.empty:
            candidates = transitions[transitions["to_stage"].isin(["waiting", "form_waiting", "technical_interview", "hr_interview"])]
            if not candidates.empty:
                top = candidates.sort_values("count", ascending=False).iloc[0]
                bottleneck = {"stage": str(top["to_stage"]), "count": int(top["count"])}

        export_path = None
        outputs: list[dict[str, Any]] = []
        files: list[str] = []
        if export:
            sheets = {
                "transitions": transitions,
                "new_candidates": new_rows.drop(columns=["_merge"], errors="ignore"),
                "dropped_candidates": dropped_rows.drop(columns=["_merge"], errors="ignore"),
                "changed_stage": progressed.drop(columns=["_merge"], errors="ignore"),
            }
            export_path = export_multiple_sheets(sheets, "candidate_stage_transitions")
            files.append(export_path)
            outputs.append(
                {
                    "type": "file",
                    "title": "candidate_stage_transitions.xlsx",
                    "description": "Iki donem arasi surec gecis analizi (transitions/new/dropped/changed).",
                    "format": "xlsx",
                    "path": export_path,
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "display": True,
                }
            )

        data = {
            "selected_files": {"a": file_registry.get_meta(file_id_a).__dict__, "b": file_registry.get_meta(file_id_b).__dict__},
            "key_columns": keys,
            "stage_columns": {"a": stage_a, "b": stage_b},
            "counts": {
                "matched": int(len(common)),
                "new": int(len(new_rows)),
                "dropped": int(len(dropped_rows)),
                "changed_stage": int(len(progressed)),
                "unchanged_stage": int(len(stayed)),
            },
            "bottleneck": bottleneck,
            "transitions_preview": transitions.head(25).to_dict(orient="records"),
            "changed_stage_preview": safe_preview(progressed.drop(columns=["_merge"], errors="ignore"), min(limit, 30)),
            "export_path": export_path,
        }
        return {"data": data, "files": files, "generated_outputs": outputs}


hr_transitions_service = HRTransitionsService()

