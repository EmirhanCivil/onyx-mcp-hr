"""Match recruiting spreadsheet rows to CV files.

We do not assume a fixed schema: columns may vary (HR, vehicles, etc).
Matching is heuristic and prioritizes:
1) email exact match
2) phone exact match
3) name similarity vs CV filename / extracted name patterns
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.exporters.excel_exporter import export_multiple_sheets
from app.services.cv_service import cv_service
from app.services.excel_service import excel_service
from app.utils.dataframe_utils import normalize_column_name, safe_preview


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")


@dataclass(frozen=True)
class MatchColumns:
    email: str
    phone: str
    name: str
    id: str


class ExcelCvMatchService:
    def match(
        self,
        file_query: str = "",
        file_id: str = "",
        limit: int = 25,
        export: bool = True,
    ) -> dict:
        excel_service.scan_uploads()
        cv_service.scan_cvs()

        selected = None
        target = file_id
        if not target:
            selected = excel_service.select_file(file_query, "candidate") or excel_service.select_file(file_query, "excel")
            target = selected["file_id"] if selected else ""
        if not target:
            raise InvalidInputError("Eslesme icin uygun aday Excel'i bulunamadi.")

        df = file_registry.get_frame(target)
        cols = self._resolve_match_columns(df)

        cv_index = _build_cv_index()

        matched_rows: list[dict[str, Any]] = []
        unmatched_rows: list[dict[str, Any]] = []
        matched_cv_ids: set[str] = set()

        for _, row in df.iterrows():
            email = _norm_email(row.get(cols.email)) if cols.email else ""
            phone = _norm_phone(row.get(cols.phone)) if cols.phone else ""
            name = _norm_name(row.get(cols.name)) if cols.name else ""
            rid = str(row.get(cols.id)).strip() if cols.id and cols.id in df.columns and not pd.isna(row.get(cols.id)) else ""

            match = None
            reason = ""
            if email and email in cv_index["by_email"]:
                match = cv_index["by_email"][email]
                reason = "email"
            elif phone and phone in cv_index["by_phone"]:
                match = cv_index["by_phone"][phone]
                reason = "phone"
            elif name:
                match, score = _best_name_match(name, cv_index["by_name"])
                if match and score >= 0.86:
                    reason = f"name_similarity:{score}"
                else:
                    match = None

            base = {
                "_row": int(row.name) + 2,
                "candidate_id": rid,
                "candidate_email": email or None,
                "candidate_phone": phone or None,
                "candidate_name": row.get(cols.name) if cols.name else None,
            }
            if match:
                matched_cv_ids.add(match["cv_id"])
                matched_rows.append(
                    {
                        **base,
                        "match_type": reason,
                        "cv_id": match["cv_id"],
                        "cv_file": match["file_name"],
                        "cv_path": match["path"],
                    }
                )
            else:
                unmatched_rows.append({**base, "match_type": None})

        # CVs that have no matching spreadsheet row.
        unmatched_cvs = []
        for item in cv_index["all"]:
            if item["cv_id"] not in matched_cv_ids:
                unmatched_cvs.append(
                    {
                        "cv_id": item["cv_id"],
                        "cv_file": item["file_name"],
                        "cv_path": item["path"],
                        "email": item.get("email") or None,
                        "phone": item.get("phone") or None,
                        "name_guess": item.get("name_guess") or None,
                    }
                )

        files: list[str] = []
        outputs: list[dict[str, Any]] = []
        export_path = None
        if export:
            sheets = {
                "matched": pd.DataFrame(matched_rows),
                "unmatched_candidates": pd.DataFrame(unmatched_rows),
                "unmatched_cvs": pd.DataFrame(unmatched_cvs),
            }
            export_path = export_multiple_sheets(sheets, "excel_cv_matching")
            files.append(export_path)
            outputs.append(
                {
                    "type": "file",
                    "title": "excel_cv_matching.xlsx",
                    "description": "Excel–CV eslesme raporu (matched/unmatched).",
                    "format": "xlsx",
                    "path": export_path,
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "display": True,
                }
            )

        data = {
            "selected_file": selected or file_registry.get_meta(target).__dict__,
            "row_count": int(len(df)),
            "resolved_columns": cols.__dict__,
            "match_summary": {
                "matched_count": int(len(matched_rows)),
                "unmatched_candidate_count": int(len(unmatched_rows)),
                "unmatched_cv_count": int(len(unmatched_cvs)),
                "match_rate_percent": round((len(matched_rows) / max(len(df), 1)) * 100, 2),
            },
            "matched_preview": matched_rows[: min(max(1, limit), 50)],
            "unmatched_candidates_preview": unmatched_rows[: min(max(1, limit), 50)],
            "unmatched_cvs_preview": unmatched_cvs[: min(max(1, limit), 50)],
            "export_path": export_path,
        }
        return {"data": data, "files": files, "generated_outputs": outputs}

    @staticmethod
    def _resolve_match_columns(df: pd.DataFrame) -> MatchColumns:
        def pick(hints: list[str]) -> str:
            return _pick_column(df, hints, required=False)

        return MatchColumns(
            email=pick(["email", "e-mail", "eposta", "mail"]),
            phone=pick(["telefon", "phone", "gsm", "mobile", "cep"]),
            name=pick(["ad soyad", "isim soyisim", "full name", "name surname", "ad", "isim"]),
            id=pick(["aday id", "candidate id", "id", "sicil", "no"]),
        )


def _pick_column(df: pd.DataFrame, hints: list[str], required: bool = True) -> str:
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


def _norm_email(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value).strip().lower()
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else ""


def _norm_phone(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value)
    m = _PHONE_RE.search(text)
    if not m:
        return ""
    digits = re.sub(r"\D", "", m.group(0))
    # keep last 10-12 digits to reduce country-prefix noise
    return digits[-12:] if len(digits) > 12 else digits


def _norm_name(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    return normalize_column_name(text)


def _best_name_match(name_norm: str, candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    best = None
    best_score = 0.0
    for item in candidates:
        cand = item.get("name_guess_norm") or ""
        if not cand:
            continue
        score = _jaccard_name(name_norm, cand)
        if score > best_score:
            best = item
            best_score = score
    return best, float(best_score)


def _jaccard_name(a: str, b: str) -> float:
    a_tokens = {t for t in a.split() if len(t) > 1}
    b_tokens = {t for t in b.split() if len(t) > 1}
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return inter / max(union, 1)


def _build_cv_index() -> dict[str, Any]:
    cv_service.scan_cvs()
    by_email: dict[str, dict[str, Any]] = {}
    by_phone: dict[str, dict[str, Any]] = {}
    by_name: list[dict[str, Any]] = []
    all_items: list[dict[str, Any]] = []

    for meta, text in cv_service.iter_cvs():
        emails = _EMAIL_RE.findall(text or "")
        phones = _PHONE_RE.findall(text or "")
        email = _norm_email(emails[0]) if emails else ""
        phone = _norm_phone(phones[0]) if phones else ""
        name_guess = _name_from_filename(meta.name)
        item = {
            "cv_id": meta.cv_id,
            "file_name": meta.name,
            "path": meta.path,
            "email": email,
            "phone": phone,
            "name_guess": name_guess,
            "name_guess_norm": normalize_column_name(name_guess),
        }
        all_items.append(item)
        if email and email not in by_email:
            by_email[email] = item
        if phone and phone not in by_phone:
            by_phone[phone] = item
        if item["name_guess_norm"]:
            by_name.append(item)

    return {"by_email": by_email, "by_phone": by_phone, "by_name": by_name, "all": all_items}


def _name_from_filename(file_name: str) -> str:
    stem = Path(file_name).stem
    cleaned = re.sub(r"^\d+[_-]?", "", stem)
    cleaned = re.sub(r"ady-\d+[_-]?", "", cleaned, flags=re.IGNORECASE)
    return cleaned.replace("_", " ").strip() or stem


excel_cv_match_service = ExcelCvMatchService()

