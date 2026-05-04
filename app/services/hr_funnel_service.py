"""Position-based funnel analysis for candidate spreadsheets."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.exporters.excel_exporter import export_multiple_sheets
from app.services.excel_service import excel_service
from app.services.hr_column_normalization_service import hr_column_normalization_service
from app.utils.dataframe_utils import normalize_column_name


_FUNNEL_STAGES = [
    ("applied", ["new", "applied", "basvuru", "başvuru", "screening"]),
    ("form", ["form_waiting", "form", "belge", "dokuman", "document"]),
    ("technical", ["technical_interview", "teknik", "case", "assignment", "challenge"]),
    ("hr", ["hr_interview", "ik gorus", "hr interview"]),
    ("positive", ["positive"]),
    ("negative", ["negative"]),
]


class HRFunnelService:
    def analyze_position_funnel(
        self,
        file_query: str = "",
        file_id: str = "",
        position_col: str = "",
        status_col: str = "",
        top_n: int = 15,
        export: bool = False,
    ) -> dict:
        excel_service.scan_uploads()
        selected = None
        target = file_id
        if not target:
            selected = excel_service.select_file(file_query, "candidate") or excel_service.select_file(file_query, "excel")
            target = selected["file_id"] if selected else ""
        if not target:
            raise InvalidInputError("Funnel analizi icin uygun aday Excel'i bulunamadi.")

        df = file_registry.get_frame(target)
        norm = hr_column_normalization_service.normalize(df)
        mapping = norm.get("canonical_mapping", {})
        pos = position_col if position_col in df.columns else mapping.get("position", "")
        status = status_col if status_col in df.columns else mapping.get("status", "")
        if not pos or not status:
            raise InvalidInputError("Pozisyon veya surec/durum kolonu bulunamadi. Kolon adlarini netlestirin.")

        work = df[[pos, status]].copy()
        work[pos] = work[pos].map(lambda v: "(empty)" if pd.isna(v) or str(v).strip() == "" else str(v).strip())
        work["_stage"] = work[status].map(lambda v: hr_column_normalization_service.normalize_status(v)["normalized"])

        # Focus on top positions.
        top_positions = work[pos].value_counts().head(max(1, min(top_n, 50))).index
        work = work[work[pos].isin(top_positions)]

        rows = []
        for pval, group in work.groupby(pos):
            total = int(len(group))
            stage_counts = group["_stage"].value_counts().to_dict()
            metrics = {"position": str(pval), "total": total}
            for key, aliases in _FUNNEL_STAGES:
                metrics[key] = int(sum(stage_counts.get(a, 0) for a in aliases))
            # Simple conversion rates (avoid division by 0)
            metrics["form_rate"] = round(metrics["form"] / total * 100, 2) if total else 0.0
            metrics["technical_rate"] = round(metrics["technical"] / total * 100, 2) if total else 0.0
            metrics["hr_rate"] = round(metrics["hr"] / total * 100, 2) if total else 0.0
            metrics["positive_rate"] = round(metrics["positive"] / total * 100, 2) if total else 0.0
            rows.append(metrics)

        table = pd.DataFrame(rows).sort_values(["total", "positive_rate"], ascending=[False, False])

        # Bottleneck: stage with high volume but low forward rate (rough)
        bottlenecks = []
        for _, r in table.head(20).iterrows():
            if r["total"] >= 10 and r["technical_rate"] < 20 and r["form_rate"] >= 30:
                bottlenecks.append({"position": r["position"], "signal": "form->technical drop", "total": int(r["total"])})
        bottlenecks = bottlenecks[:10]

        export_path = None
        files: list[str] = []
        outputs: list[dict[str, Any]] = []
        if export:
            export_path = export_multiple_sheets({"position_funnel": table}, "position_funnel")
            files.append(export_path)
            outputs.append(
                {
                    "type": "file",
                    "title": "position_funnel.xlsx",
                    "description": "Pozisyon bazli funnel tablosu.",
                    "format": "xlsx",
                    "path": export_path,
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "display": True,
                }
            )

        data = {
            "selected_file": selected or file_registry.get_meta(target).__dict__,
            "resolved_columns": {"position": pos, "status": status},
            "position_count": int(len(table)),
            "top_positions": table.head(10).to_dict(orient="records"),
            "bottleneck_signals": bottlenecks,
            "export_path": export_path,
            "column_normalization": norm,
        }
        return {"data": data, "files": files, "generated_outputs": outputs}


hr_funnel_service = HRFunnelService()

