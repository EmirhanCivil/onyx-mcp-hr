"""Smart file selection for HR workflows.

This is an Onyx-friendly helper: users often don't know file_id, sheet names, or exact filenames.
We select the most relevant file and also return alternative candidates when multiple matches exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.file_registry import file_registry
from app.services.cv_service import cv_service
from app.services.excel_service import excel_service
from app.utils.dataframe_utils import normalize_column_name


@dataclass(frozen=True)
class SelectionResult:
    selection_type: str  # cv_library | spreadsheet
    category: str  # cv | candidate | excel | survey | spreadsheet
    selected: dict[str, Any] | None
    alternatives: list[dict[str, Any]]
    warnings: list[str]


class HRFileSelectionService:
    def auto_select(self, query: str = "", preferred: str = "", max_alternatives: int = 5) -> dict:
        excel_service.scan_uploads()
        cv_service.scan_cvs()

        qn = normalize_column_name(query)
        preferred_norm = normalize_column_name(preferred)
        warnings: list[str] = []

        # Decide target domain.
        if preferred_norm in {"cv", "cvs", "resume"} or any(t in qn for t in ("cv", "ozgecmis", "özgecmis", "resume")):
            selected = {"type": "cv_library", "category": "cv", "selected": {"cv_count": cv_service.scan_cvs().get("loaded_count", 0)}, "alternatives": []}
            if selected["selected"]["cv_count"] == 0:
                warnings.append("CV kutuphanesi bos gorunuyor. data/uploads/cv altini kontrol edin.")
            return SelectionResult("cv_library", "cv", selected["selected"], [], warnings).__dict__

        # Survey vs candidate/excel
        wants_survey = preferred_norm == "survey" or any(t in qn for t in ("anket", "survey", "memnuniyet", "skor", "yorum", "engagement"))
        wants_candidate = preferred_norm in {"candidate", "aday"} or any(t in qn for t in ("aday", "basvuru", "pipeline", "funnel", "form", "ik gorus", "teknik gorus"))
        category = "survey" if wants_survey else ("candidate" if wants_candidate else "spreadsheet")

        matches = excel_service.find_files(query, category)["matches"]
        selected = matches[0] if matches else excel_service.select_file(query, category)
        alternatives = matches[1:max_alternatives] if matches else []
        if not selected:
            warnings.append("Uygun dosya bulunamadi. uploads/excel veya uploads/survey altini kontrol edin.")
            return SelectionResult("spreadsheet", category, None, [], warnings).__dict__

        # If selected type doesn't align with intent, warn.
        selected_cat = normalize_column_name((selected.get("tags") or {}).get("category") or selected.get("category") or "")
        if wants_survey and selected_cat and selected_cat != "survey":
            warnings.append(f"Secilen dosya survey gibi gorunmuyor (category={selected_cat}). Yanlis dosya secilmis olabilir.")
        if wants_candidate and selected_cat and selected_cat == "survey":
            warnings.append("Secilen dosya survey gibi gorunuyor; aday havuzu yerine anket secilmis olabilir.")

        return SelectionResult("spreadsheet", category, selected, alternatives, warnings).__dict__


hr_file_selection_service = HRFileSelectionService()

