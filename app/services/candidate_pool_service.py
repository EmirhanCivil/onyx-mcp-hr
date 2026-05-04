"""Candidate pool analytics for recruiting spreadsheets.

Goal: produce decision-support summaries without dumping raw tables into the LLM.
This service is intentionally column-name-agnostic; it uses fuzzy hint matching
to locate "stage/status", "school/university", "city/location" etc when present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.analyzers.duplicate_analyzer import find_duplicates
from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.exporters.excel_exporter import export_multiple_sheets
from app.services.excel_service import excel_service
from app.utils.column_detector import detect_columns
from app.utils.dataframe_utils import dataframe_profile, normalize_column_name, safe_preview


_FIELD_HINTS: dict[str, list[str]] = {
    "status": [
        "aday durumu",
        "basvuru durumu",
        "form durumu",
        "status",
        "stage",
        "phase",
        "step",
        "asama",
        "durum",
        "pipeline",
    ],
    "university": ["universite", "university", "school", "okul"],
    "major": ["bolum", "bölüm", "major", "department", "program", "field of study"],
    # Avoid ultra-short tokens like "il" (province) because they cause false matches (e.g. "emaIL").
    "city": ["sehir", "şehir", "city", "location", "lokasyon", "province"],
    "experience": ["deneyim", "experience", "kidem", "kıdem", "years", "year", "tecrube", "tecrübe"],
    "age": ["yas", "yaş", "age"],
    "military": ["askerlik", "military"],
    "email": ["email", "e-mail", "eposta", "e posta", "mail"],
    "phone": ["telefon", "phone", "gsm", "mobile", "cep"],
    "name": ["ad soyad", "isim soyisim", "name surname", "full name", "ad", "isim", "soyad", "surname", "last name"],
    "id": ["id", "record id", "candidate id", "applicant id", "unique id", "sicil", "numara", "number"],
}


@dataclass(frozen=True)
class ResolvedColumns:
    status: str
    university: str
    major: str
    city: str
    experience: str
    age: str
    military: str
    email: str
    phone: str
    name: str
    id: str


class CandidatePoolService:
    """High-level pool analytics on top of the spreadsheet registry."""

    def analyze(
        self,
        file_query: str = "",
        file_id: str = "",
        limit: int = 20,
        export: bool = False,
    ) -> dict:
        excel_service.scan_uploads()
        selected = None
        target = file_id
        if not target:
            # Prefer "candidate" category, otherwise fallback to generic excel.
            selected = excel_service.select_file(file_query, "candidate") or excel_service.select_file(file_query, "excel")
            target = selected["file_id"] if selected else ""
        if not target:
            raise InvalidInputError("Aday havuzu icin uygun Excel bulunamadi. uploads/excel altini kontrol edin.")

        df = file_registry.get_frame(target)
        profile = dataframe_profile(df)
        detected = detect_columns(df)
        resolved = self._resolve_columns(df)

        # Core distributions (top values).
        distributions = {
            "status": _value_counts(df, resolved.status, 25),
            "university": _value_counts(df, resolved.university, 20),
            "major": _value_counts(df, resolved.major, 20),
            "city": _value_counts(df, resolved.city, 20),
            "experience": _value_counts(df, resolved.experience, 20),
            "age": _value_counts(df, resolved.age, 20),
            "military": _value_counts(df, resolved.military, 20),
        }

        # Missingness on key columns.
        key_fields = [
            ("status", resolved.status),
            ("university", resolved.university),
            ("major", resolved.major),
            ("city", resolved.city),
            ("experience", resolved.experience),
            ("age", resolved.age),
            ("military", resolved.military),
            ("email", resolved.email),
            ("phone", resolved.phone),
            ("name", resolved.name),
            ("id", resolved.id),
        ]
        missing_focus = []
        for label, col in key_fields:
            if col and col in df.columns:
                rate = profile["missing_rates_percent"].get(col)
                missing_focus.append({"field": label, "column": col, "missing_rate_percent": rate})
        missing_focus = sorted(
            [item for item in missing_focus if item.get("missing_rate_percent") is not None],
            key=lambda item: item["missing_rate_percent"],
            reverse=True,
        )

        # Duplicate detection (prefer stable identifiers).
        dup_keys = self._choose_duplicate_keys(resolved, detected, df)
        duplicate_report = find_duplicates(df, dup_keys or None, keep="first")

        files: list[str] = []
        outputs: list[dict[str, Any]] = []
        export_path = None
        if export:
            sheets = {}
            # Duplicate rows (if any)
            if duplicate_report.get("duplicate_row_count", 0):
                dup_preview = pd.DataFrame(duplicate_report.get("rows_preview", []))
                if not dup_preview.empty:
                    sheets["duplicates_preview"] = dup_preview
            # Missing email / phone (common ops requirement)
            for tag, col in (("missing_email", resolved.email), ("missing_phone", resolved.phone)):
                if col and col in df.columns:
                    series = df[col].map(lambda v: "" if pd.isna(v) else str(v).strip())
                    miss = df[series == ""].copy()
                    if not miss.empty:
                        sheets[tag] = miss
            if sheets:
                export_path = export_multiple_sheets(sheets, "candidate_pool_exports")
                files.append(export_path)
                outputs.append(
                    {
                        "type": "file",
                        "title": "candidate_pool_exports.xlsx",
                        "description": "Aday havuzu: duplicate/missing export paketleri.",
                        "format": "xlsx",
                        "path": export_path,
                        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "display": True,
                    }
                )

        data = {
            "selected_file": selected or file_registry.get_meta(target).__dict__,
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "detected_columns": detected,
            "resolved_columns": resolved.__dict__,
            "distributions": distributions,
            "missing_focus": missing_focus[:12],
            "duplicate_keys_used": dup_keys,
            "duplicates": duplicate_report,
            "preview": safe_preview(df, min(max(1, limit), 30)),
            "export_path": export_path,
        }
        return {"data": data, "files": files, "generated_outputs": outputs}

    @staticmethod
    def _resolve_columns(df: pd.DataFrame) -> ResolvedColumns:
        def pick(field: str) -> str:
            return _pick_column(df, _FIELD_HINTS.get(field, []), required=False)

        return ResolvedColumns(
            status=pick("status"),
            university=pick("university"),
            major=pick("major"),
            city=pick("city"),
            experience=pick("experience"),
            age=pick("age"),
            military=pick("military"),
            email=pick("email"),
            phone=pick("phone"),
            name=pick("name"),
            id=pick("id"),
        )

    @staticmethod
    def _choose_duplicate_keys(resolved: ResolvedColumns, detected: dict, df: pd.DataFrame) -> list[str]:
        # Prefer stable identifiers: email / phone / strong key candidates (high uniqueness).
        keys: list[str] = []

        def looks_like_identifier(col: str) -> bool:
            norm = normalize_column_name(col)
            return any(token in norm for token in ("email", "mail", "telefon", "phone", "gsm", "sicil", "tckn", "kimlik", "candidate id", "record id", "unique id", "id"))

        for col in (resolved.email, resolved.phone):
            if col and col in df.columns:
                keys.append(col)

        # Only accept resolved.id if it truly looks like an identifier and is reasonably unique.
        if resolved.id and resolved.id in df.columns and looks_like_identifier(resolved.id):
            series = df[resolved.id]
            unique_rate = float(series.dropna().nunique() / max(len(df), 1))
            if unique_rate >= 0.8:
                keys.append(resolved.id)

        keys = list(dict.fromkeys([k for k in keys if k]))
        if keys:
            return keys[:2]

        # Fall back to detector key candidates (already ranked).
        candidates = [item["column"] for item in detected.get("key_candidates", []) if item.get("confidence", 0) >= 0.75]
        candidates = [c for c in candidates if c in df.columns and looks_like_identifier(c)]
        return candidates[:2]


def _pick_column(df: pd.DataFrame, hints: list[str], required: bool = True) -> str:
    if not hints:
        if required:
            raise InvalidInputError("Kolon bulunamadi: ipucu verilmedi.")
        return ""
    scored: list[tuple[int, str]] = []
    for column in df.columns:
        col = str(column)
        norm = normalize_column_name(col)
        score = 0
        for idx, hint in enumerate(hints):
            hint_norm = normalize_column_name(hint)
            bonus = (len(hints) - idx) * 4
            if hint_norm == norm:
                score += len(hint_norm) + 120 + bonus
            elif hint_norm and hint_norm in norm:
                score += len(hint_norm) + 30 + bonus
            for tok in hint_norm.split():
                if tok and tok in norm:
                    score += len(tok) + bonus
        scored.append((score, col))
    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    if required:
        raise InvalidInputError(f"Kolon bulunamadi. Ipuclari: {', '.join(hints[:6])}")
    return ""


def _value_counts(df: pd.DataFrame, column: str, limit: int) -> list[dict[str, Any]]:
    if not column or column not in df.columns:
        return []
    cleaned = df[column].map(lambda item: "(empty)" if pd.isna(item) or str(item).strip() == "" else str(item).strip())
    counts = cleaned.value_counts().head(max(1, min(limit, 50)))
    total = max(int(len(df)), 1)
    out = []
    for value, cnt in counts.items():
        out.append({"value": str(value), "count": int(cnt), "percent": round(int(cnt) / total * 100, 2)})
    return out


candidate_pool_service = CandidatePoolService()
