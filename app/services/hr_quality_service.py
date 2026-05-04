"""HR data quality scoring (0-100) for candidate spreadsheets.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.analyzers.duplicate_analyzer import find_duplicates
from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.services.excel_cv_match_service import excel_cv_match_service
from app.services.excel_service import excel_service
from app.services.hr_column_normalization_service import hr_column_normalization_service
from app.utils.dataframe_utils import dataframe_profile


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class HRQualityService:
    def score(
        self,
        file_query: str = "",
        file_id: str = "",
        include_cv_match: bool = True,
        max_invalid_examples: int = 10,
    ) -> dict:
        excel_service.scan_uploads()
        selected = None
        target = file_id
        if not target:
            selected = excel_service.select_file(file_query, "candidate") or excel_service.select_file(file_query, "excel")
            target = selected["file_id"] if selected else ""
        if not target:
            raise InvalidInputError("Kalite skoru icin uygun aday Excel'i bulunamadi.")

        df = file_registry.get_frame(target)
        profile = dataframe_profile(df)
        norm = hr_column_normalization_service.normalize(df)
        mapping = norm.get("canonical_mapping", {})

        # Missingness penalties on key columns
        key_fields = ["full_name", "email", "phone", "status", "position", "department", "university", "city"]
        missing_rates = {}
        missing_penalty = 0.0
        for field in key_fields:
            col = mapping.get(field, "")
            if not col or col not in df.columns:
                continue
            rate = float(profile["missing_rates_percent"].get(col, 0.0))
            missing_rates[field] = {"column": col, "missing_rate_percent": rate}
            # Weight: identity fields penalize more.
            weight = 1.6 if field in {"email", "phone", "full_name"} else 1.0
            missing_penalty += min(35.0, rate * 0.35 * weight)

        # Duplicate penalty (prefer email/phone/id)
        dup_keys = [c for c in (mapping.get("email"), mapping.get("phone"), mapping.get("candidate_id")) if c and c in df.columns]
        dup_keys = list(dict.fromkeys(dup_keys))[:2]
        dup_report = find_duplicates(df, dup_keys or None)
        dup_rate = (dup_report.get("duplicate_row_count", 0) / max(len(df), 1)) * 100.0
        duplicate_penalty = min(30.0, dup_rate * 0.6)

        # Invalid format checks
        invalid = {"email": [], "phone": [], "birth_date": []}
        invalid_penalty = 0.0

        email_col = mapping.get("email")
        if email_col and email_col in df.columns:
            for idx, val in df[email_col].items():
                if pd.isna(val) or str(val).strip() == "":
                    continue
                if not _EMAIL_RE.match(str(val).strip().lower()):
                    invalid["email"].append({"row": int(idx) + 2, "value": str(val)[:120]})
            if invalid["email"]:
                invalid_penalty += min(20.0, (len(invalid["email"]) / max(len(df), 1)) * 100.0 * 0.7)

        phone_col = mapping.get("phone")
        if phone_col and phone_col in df.columns:
            for idx, val in df[phone_col].items():
                if pd.isna(val) or str(val).strip() == "":
                    continue
                digits = re.sub(r"\D", "", str(val))
                if len(digits) < 10:
                    invalid["phone"].append({"row": int(idx) + 2, "value": str(val)[:120]})
            if invalid["phone"]:
                invalid_penalty += min(15.0, (len(invalid["phone"]) / max(len(df), 1)) * 100.0 * 0.5)

        dob_col = mapping.get("birth_date")
        if dob_col and dob_col in df.columns:
            parsed = pd.to_datetime(df[dob_col], errors="coerce", dayfirst=True)
            invalid_idx = parsed.isna() & df[dob_col].notna() & (df[dob_col].astype(str).str.strip() != "")
            if invalid_idx.any():
                for idx in df[invalid_idx].index[: max_invalid_examples]:
                    invalid["birth_date"].append({"row": int(idx) + 2, "value": str(df.loc[idx, dob_col])[:120]})
                invalid_penalty += min(10.0, (int(invalid_idx.sum()) / max(len(df), 1)) * 100.0 * 0.4)

        # CV matching penalty (optional)
        cv_match_penalty = 0.0
        cv_match_summary = {}
        if include_cv_match:
            match = excel_cv_match_service.match(file_id=target, export=False, limit=10)
            cv_match_summary = match.get("data", {}).get("match_summary", {}) or {}
            unmatched = float(cv_match_summary.get("unmatched_candidate_count", 0))
            cv_match_penalty = min(20.0, (unmatched / max(len(df), 1)) * 100.0 * 0.35)

        # Score composition
        raw_penalty = missing_penalty + duplicate_penalty + invalid_penalty + cv_match_penalty
        score = max(0.0, 100.0 - raw_penalty)
        score = round(float(score), 1)

        actions = []
        if missing_rates:
            top_missing = sorted(missing_rates.items(), key=lambda kv: kv[1]["missing_rate_percent"], reverse=True)[:3]
            for field, item in top_missing:
                if item["missing_rate_percent"] >= 5:
                    actions.append(f"{field} alaninda %{item['missing_rate_percent']} eksik veri var ({item['column']}). Kaynak form/entegrasyon zorunluluklarini kontrol edin.")
        if dup_report.get("duplicate_row_count", 0):
            actions.append("Duplicate adaylar tespit edildi. Email/telefon/id uzerinden tekillestirme akisi calistirin (deduplicate_spreadsheet).")
        if invalid["email"]:
            actions.append("Gecersiz email formatlari var. Email validation/temizlik kurali ekleyin veya kaynak sistemi duzeltin.")
        if invalid["phone"]:
            actions.append("Gecersiz telefon formatlari var. Telefonu normalize eden bir format standardi belirleyin.")
        if include_cv_match and cv_match_summary.get("unmatched_candidate_count", 0):
            actions.append("CV eslesmeyen adaylar var. CV eksik adaylari ayrica export edip tamamlama sureci olusturun.")

        data = {
            "selected_file": selected or file_registry.get_meta(target).__dict__,
            "row_count": int(len(df)),
            "quality_score_0_100": score,
            "components": {
                "missing_penalty": round(float(missing_penalty), 2),
                "duplicate_penalty": round(float(duplicate_penalty), 2),
                "invalid_penalty": round(float(invalid_penalty), 2),
                "cv_match_penalty": round(float(cv_match_penalty), 2),
            },
            "missing_rates_key_fields": missing_rates,
            "duplicates": {
                "keys_used": dup_keys,
                "duplicate_row_count": dup_report.get("duplicate_row_count", 0),
                "duplicate_group_count": dup_report.get("duplicate_group_count", 0),
            },
            "invalid_formats": {
                "invalid_email_count": len(invalid["email"]),
                "invalid_phone_count": len(invalid["phone"]),
                "invalid_birth_date_count": len(invalid["birth_date"]),
                "examples": {k: v[:max_invalid_examples] for k, v in invalid.items()},
            },
            "cv_match_summary": cv_match_summary,
            "recommended_actions": actions[:8],
            "column_normalization": norm,
        }
        return data


hr_quality_service = HRQualityService()
