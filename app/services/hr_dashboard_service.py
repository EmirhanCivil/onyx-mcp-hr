"""HR dashboard-style overview for candidate pools."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.services.candidate_pool_service import candidate_pool_service
from app.services.excel_service import excel_service
from app.services.hr_column_normalization_service import hr_column_normalization_service
from app.services.hr_quality_service import hr_quality_service
from app.utils.dataframe_utils import normalize_column_name


class HRDashboardService:
    def overview(self, file_query: str = "", file_id: str = "", limit: int = 15, include_quality: bool = True) -> dict:
        excel_service.scan_uploads()
        selected = None
        target = file_id
        if not target:
            selected = excel_service.select_file(file_query, "candidate") or excel_service.select_file(file_query, "excel")
            target = selected["file_id"] if selected else ""
        if not target:
            raise InvalidInputError("Dashboard icin uygun aday Excel'i bulunamadi.")

        df = file_registry.get_frame(target)
        norm = hr_column_normalization_service.normalize(df)
        mapping = norm.get("canonical_mapping", {})
        status_col = mapping.get("status", "")
        position_col = mapping.get("position", "")
        university_col = mapping.get("university", "")
        city_col = mapping.get("city", "")
        department_col = mapping.get("department", "")

        # Status bucket counts.
        status_bucket_counts = {}
        if status_col and status_col in df.columns:
            buckets = df[status_col].map(lambda v: hr_column_normalization_service.normalize_status(v)["normalized"])
            status_bucket_counts = buckets.value_counts().to_dict()

        # Top segments
        def top(col: str) -> list[dict[str, Any]]:
            if not col or col not in df.columns:
                return []
            cleaned = df[col].map(lambda x: "(empty)" if pd.isna(x) or str(x).strip() == "" else str(x).strip())
            counts = cleaned.value_counts().head(max(1, min(limit, 25)))
            return [{"value": str(k), "count": int(v)} for k, v in counts.items()]

        pool = candidate_pool_service.analyze(file_id=target, limit=10, export=False)["data"]

        quality = {}
        if include_quality:
            quality = hr_quality_service.score(file_id=target, include_cv_match=True)

        return {
            "selected_file": selected or file_registry.get_meta(target).__dict__,
            "row_count": int(len(df)),
            "status_buckets": status_bucket_counts,
            "top_segments": {
                "position": top(position_col),
                "university": top(university_col),
                "city": top(city_col),
                "department": top(department_col),
            },
            "missing_and_duplicates": {
                "missing_focus": pool.get("missing_focus", [])[:10],
                "duplicate_row_count": (pool.get("duplicates") or {}).get("duplicate_row_count", 0),
            },
            "quality_score": quality.get("quality_score_0_100") if quality else None,
            "quality_actions": quality.get("recommended_actions", [])[:5] if quality else [],
            "column_normalization": norm,
        }


hr_dashboard_service = HRDashboardService()

