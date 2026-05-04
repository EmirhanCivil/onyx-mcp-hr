"""Compare candidate segments (school/city/major/position/department/source) against outcome-style metrics."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.exporters.excel_exporter import export_multiple_sheets
from app.services.excel_service import excel_service
from app.services.hr_column_normalization_service import hr_column_normalization_service


class HRSegmentCompareService:
    def compare(
        self,
        file_query: str = "",
        file_id: str = "",
        segment_field: str = "university",
        top_n: int = 20,
        export: bool = False,
    ) -> dict:
        excel_service.scan_uploads()
        selected = None
        target = file_id
        if not target:
            selected = excel_service.select_file(file_query, "candidate") or excel_service.select_file(file_query, "excel")
            target = selected["file_id"] if selected else ""
        if not target:
            raise InvalidInputError("Segment karsilastirma icin uygun aday Excel'i bulunamadi.")

        df = file_registry.get_frame(target)
        norm = hr_column_normalization_service.normalize(df)
        mapping = norm.get("canonical_mapping", {})

        seg_col = mapping.get(segment_field, "")
        status_col = mapping.get("status", "")
        if not seg_col or seg_col not in df.columns:
            raise InvalidInputError(f"Segment kolonu bulunamadi: {segment_field}. normalize_hr_columns ile mapping bakabilirsiniz.")
        if not status_col or status_col not in df.columns:
            raise InvalidInputError("Surec/durum kolonu bulunamadi. Segment KPI hesaplamak icin status gerekli.")

        work = df[[seg_col, status_col]].copy()
        work[seg_col] = work[seg_col].map(lambda v: "(empty)" if pd.isna(v) or str(v).strip() == "" else str(v).strip())
        work["_stage"] = work[status_col].map(lambda v: hr_column_normalization_service.normalize_status(v)["normalized"])

        top_segments = work[seg_col].value_counts().head(max(1, min(top_n, 50))).index
        work = work[work[seg_col].isin(top_segments)]

        rows = []
        for seg, g in work.groupby(seg_col):
            total = int(len(g))
            stage_counts = g["_stage"].value_counts().to_dict()
            metrics = {
                "segment": str(seg),
                "total": total,
                "form_waiting": int(stage_counts.get("form_waiting", 0)),
                "technical_interview": int(stage_counts.get("technical_interview", 0)),
                "hr_interview": int(stage_counts.get("hr_interview", 0)),
                "positive": int(stage_counts.get("positive", 0)),
                "negative": int(stage_counts.get("negative", 0)),
            }
            metrics["technical_rate"] = round(metrics["technical_interview"] / total * 100, 2) if total else 0.0
            metrics["hr_rate"] = round(metrics["hr_interview"] / total * 100, 2) if total else 0.0
            metrics["positive_rate"] = round(metrics["positive"] / total * 100, 2) if total else 0.0
            rows.append(metrics)

        table = pd.DataFrame(rows).sort_values(["total", "positive_rate"], ascending=[False, False])

        export_path = None
        files: list[str] = []
        outputs: list[dict[str, Any]] = []
        if export:
            export_path = export_multiple_sheets({"segment_comparison": table}, "segment_comparison")
            files.append(export_path)
            outputs.append(
                {
                    "type": "file",
                    "title": "segment_comparison.xlsx",
                    "description": "Segment karsilastirma tablosu.",
                    "format": "xlsx",
                    "path": export_path,
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "display": True,
                }
            )

        data = {
            "selected_file": selected or file_registry.get_meta(target).__dict__,
            "segment_field": segment_field,
            "resolved_columns": {"segment": seg_col, "status": status_col},
            "segments_preview": table.head(25).to_dict(orient="records"),
            "export_path": export_path,
            "column_normalization": norm,
        }
        return {"data": data, "files": files, "generated_outputs": outputs}


hr_segment_compare_service = HRSegmentCompareService()

