"""Root-cause style analysis for surveys: relate low score dimensions with comment themes and groups."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.services.survey_analysis_service import survey_analysis_service
from app.utils.column_detector import detect_columns
from app.utils.dataframe_utils import normalize_column_name


class SurveyRootCauseService:
    def analyze(self, file_id: str, min_group_size: int = 5, low_score_threshold: float | None = None, limit: int = 10) -> dict:
        df = file_registry.get_frame(file_id)
        detected = detect_columns(df)
        score_cols = detected.get("likely_score_columns") or detected.get("numeric_columns") or []
        group_cols = detected.get("group_columns") or []
        comment_cols = detected.get("comment_columns") or []
        if not score_cols:
            raise InvalidInputError("Skor kolonu bulunamadi; root cause analizi icin sayisal skorlar gerekli.")
        if not group_cols:
            raise InvalidInputError("Grup/Departman kolonu bulunamadi; root cause analizi icin grup kolonu gerekli.")

        group_col = group_cols[0]
        scores = score_cols[:8]

        group = survey_analysis_service.by_group(file_id, group_col, ",".join(scores), min_group_size)
        comments = survey_analysis_service.comments(file_id, ",".join(comment_cols[:3])) if comment_cols else {}

        # Identify low dimensions
        overall = survey_analysis_service.overview(file_id).get("overall_metrics", {})
        lows = overall.get("lowest_score_columns", [])[:5]
        threshold = low_score_threshold
        if threshold is None:
            # heuristic: if 1-5 scale, set 3.0; if 1-10 scale set 6.0
            max_mean = max((item.get("mean") or 0) for item in overall.get("highest_score_columns", [])[:3]) if overall else 0
            threshold = 3.0 if max_mean and max_mean <= 5.5 else 6.0

        risk_groups = (group.get("lowest_groups") or [])[: max(5, limit)]
        risk_themes = (comments.get("negative_themes") or [])[:limit]

        # Coarse root cause narrative: map low dims to themes.
        root_causes = []
        theme_names = [normalize_column_name(t.get("theme", "")) for t in risk_themes]
        for dim in lows:
            dim_name = str(dim.get("column"))
            dim_norm = normalize_column_name(dim_name)
            related = []
            for t, raw in zip(theme_names, risk_themes):
                if t and (t in dim_norm or dim_norm in t):
                    related.append(raw)
            if not related:
                related = risk_themes[:3]
            root_causes.append(
                {
                    "dimension": dim_name,
                    "mean": dim.get("mean"),
                    "likely_related_themes": related[:5],
                    "hypothesis": "Dusuk skor boyutu ile tekrar eden olumsuz tema sinyalleri birlikte ele alinmali.",
                }
            )

        actions = []
        for rg in risk_groups[:5]:
            actions.append(
                {
                    "group": rg.get("group"),
                    "recommended_action": "Bu grupta en dusuk 2 skor boyutu icin kok neden oturumu + aksiyon sahibi belirleyin.",
                    "timeframe": "0-30 gun",
                }
            )
        if root_causes:
            actions.append(
                {
                    "group": "Genel",
                    "recommended_action": "Tema bazli aksiyonlari 30-60 gun icinde pilotla ve 60-90 gun mini olcumle etkiyi dogrula.",
                    "timeframe": "30-90 gun",
                }
            )

        return {
            "group_col": group_col,
            "score_columns": scores,
            "low_score_threshold": threshold,
            "risk_groups": risk_groups[:limit],
            "negative_themes": risk_themes,
            "root_cause_hypotheses": root_causes[:limit],
            "recommended_actions": actions[:8],
        }


survey_root_cause_service = SurveyRootCauseService()

