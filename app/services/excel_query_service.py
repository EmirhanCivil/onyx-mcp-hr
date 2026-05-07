"""Full-scan spreadsheet querying with structured conditions and exact counts.

This service is designed for MCP tools: it never dumps whole tables into the LLM.
It always computes matched_count over the full dataset, and only returns a small sample
unless the user explicitly requests an export.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from app.analyzers.diff_analyzer import _normalize_compare_value
from app.core.exceptions import InvalidInputError
from app.core.file_registry import file_registry
from app.exporters.excel_exporter import export_dataframe
from app.utils.dataframe_utils import normalize_column_name, safe_preview


SUPPORTED_OPERATORS = {
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "greater_than",
    "less_than",
    "greater_or_equal",
    "less_or_equal",
    "between",
    "in",
    "not_in",
    "is_empty",
    "is_not_empty",
}

SUPPORTED_LOGIC = {"AND", "OR"}
SUPPORTED_RETURN_MODES = {"count", "sample", "export", "summary"}

_TEXT_OPS = {"equals", "not_equals", "contains", "not_contains", "starts_with", "ends_with", "in", "not_in"}
_ORDERING_OPS = {"greater_than", "less_than", "greater_or_equal", "less_or_equal", "between"}


@dataclass(frozen=True)
class ResolvedField:
    requested: str
    resolved: str
    confidence: float
    strategy: str


class ExcelQueryService:
    """Query large spreadsheets via full scan without returning raw data to the LLM."""

    def query_rows(
        self,
        file_id: str,
        structured_query: dict | None = None,
        natural_query: str = "",
        return_mode: str = "sample",
        sample_limit: int = 10,
        export: bool = False,
    ) -> dict:
        df = file_registry.get_frame(file_id)

        query = structured_query or self._infer_structured_query(natural_query)
        query = query or {}

        logic = str(query.get("logic") or "AND").strip().upper()
        if logic not in SUPPORTED_LOGIC:
            raise InvalidInputError(f"Unsupported logic: {logic}")

        mode = str(query.get("return_mode") or return_mode or "sample").strip().lower()
        if mode not in SUPPORTED_RETURN_MODES:
            raise InvalidInputError(f"Unsupported return_mode: {mode}")

        limit = int(query.get("sample_limit") or sample_limit or 10)
        limit = max(0, min(limit, 200))

        conditions = query.get("conditions") or []
        if not isinstance(conditions, list):
            raise InvalidInputError("conditions must be a list.")
        if not conditions:
            raise InvalidInputError("At least 1 condition is required (conditions or natural_query).")

        resolved_fields: dict[str, str] = {}
        resolutions: list[ResolvedField] = []
        applied_conditions: list[dict[str, Any]] = []
        warnings: list[str] = []

        column_conf_threshold = 0.62

        numeric_cols = set(df.select_dtypes(include="number").columns)
        date_cols = set(df.select_dtypes(include=["datetime", "datetimetz"]).columns)
        text_cols = [str(c) for c in df.columns if c not in numeric_cols and c not in date_cols]

        masks: list[pd.Series] = []
        for item in conditions:
            if not isinstance(item, dict):
                raise InvalidInputError("Invalid condition: expected an object/dict.")

            field = str(item.get("field") or "").strip()
            operator = str(item.get("operator") or "").strip().lower()
            value = item.get("value")
            value_to = item.get("value_to")

            if operator not in SUPPORTED_OPERATORS:
                raise InvalidInputError(f"Unsupported operator: {operator}")

            # Support value-only conditions (field omitted) by searching across all text-like columns.
            if not field:
                if operator not in _TEXT_OPS and operator not in {"is_empty", "is_not_empty"}:
                    raise InvalidInputError("Field-less conditions only support text operators or is_empty/is_not_empty.")
                requested_key = str(value) if value is not None else "(empty)"
                resolved_fields[requested_key] = "*"
                resolutions.append(ResolvedField(requested_key, "*", 1.0, "any_field"))
                mask = self._any_field_mask(df, text_cols, operator, value, value_to)
                masks.append(mask)
                applied_conditions.append(
                    {
                        "field": "",
                        "resolved_field": "*",
                        "operator": operator,
                        "value": value,
                        "value_to": value_to,
                    }
                )
                continue

            resolved = self._resolve_column(df, field)

            # If the user likely provided a value-only phrase (natural query fallback where field == value),
            # and we cannot confidently map it to a column, search across all columns instead of picking a weak match.
            is_value_only_phrase = isinstance(value, str) and normalize_column_name(value) == normalize_column_name(field)
            if (
                resolved.confidence < column_conf_threshold
                and is_value_only_phrase
                and operator in {"contains", "equals", "starts_with", "ends_with"}
            ):
                warnings.append(
                    f"Column match is ambiguous for '{field}' (best='{resolved.resolved}', confidence={resolved.confidence}). "
                    "Falling back to row-level search across all columns for this term."
                )
                resolved_fields[field] = "*"
                resolutions.append(ResolvedField(field, "*", 1.0, "any_field_fallback"))
                mask = self._any_field_mask(df, text_cols, operator, value, value_to)
                masks.append(mask)
                applied_conditions.append(
                    {
                        "field": field,
                        "resolved_field": "*",
                        "operator": operator,
                        "value": value,
                        "value_to": value_to,
                    }
                )
                continue

            resolutions.append(resolved)
            if resolved.confidence < column_conf_threshold:
                warnings.append(
                    f"Column match is ambiguous: '{field}' -> '{resolved.resolved}' (confidence={resolved.confidence}). "
                    "For maximum accuracy, pass the exact column name in structured_query."
                )
            resolved_fields[field] = resolved.resolved

            mask = self._condition_mask(df, resolved.resolved, operator, value, value_to)
            masks.append(mask)
            applied_conditions.append(
                {
                    "field": field,
                    "resolved_field": resolved.resolved,
                    "operator": operator,
                    "value": value,
                    "value_to": value_to,
                }
            )

        per_condition_counts = [int(m.sum()) for m in masks]

        if logic == "AND":
            final_mask = pd.Series(True, index=df.index)
            for mask in masks:
                final_mask &= mask
        else:
            final_mask = pd.Series(False, index=df.index)
            for mask in masks:
                final_mask |= mask

        matched_df = df[final_mask].copy()
        matched_count = int(final_mask.sum())

        diagnostic: dict[str, Any] = {}
        if matched_count == 0:
            diagnostic = self._build_zero_result_diagnostic(
                df, applied_conditions, per_condition_counts, logic
            )

        export_requested = bool(query.get("export")) or export or mode == "export"
        export_path = None
        generated_outputs: list[dict[str, Any]] = []
        if export_requested and matched_count:
            export_path = export_dataframe(matched_df, "query_results")
            generated_outputs.append(
                {
                    "type": "file",
                    "title": "query_results.xlsx",
                    "description": "All matched rows (export).",
                    "format": "xlsx",
                    "path": export_path,
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "display": True,
                }
            )

        sample_rows: list[dict] = []
        returned_rows_count = 0
        if mode in {"sample", "export"} and limit > 0 and matched_count:
            sample_rows = safe_preview(matched_df, limit)
            returned_rows_count = len(sample_rows)

        summary: dict[str, Any] = {}
        if mode == "summary":
            summary = self._summary(matched_df, resolutions)

        data = {
            "scan_mode": "full",
            "is_result_complete": True,
            "total_rows_scanned": int(len(df)),
            "matched_count": matched_count,
            "returned_rows_count": returned_rows_count,
            "return_limit": limit,
            "logic": logic,
            "resolved_fields": resolved_fields,
            "conditions_applied": applied_conditions,
            "per_condition_counts": per_condition_counts,
            "sample_rows": sample_rows,
            "summary": summary,
            "export_path": export_path,
            "zero_result_diagnostic": diagnostic,
        }
        return {
            "data": data,
            "warnings": warnings,
            "generated_outputs": generated_outputs,
        }

    @staticmethod
    def _normalize_text(value: object) -> str:
        return normalize_column_name(_normalize_compare_value(value))

    def _resolve_column(self, df: pd.DataFrame, requested_field: str) -> ResolvedField:
        req_norm = normalize_column_name(requested_field)
        if not req_norm:
            return ResolvedField(requested_field, str(df.columns[0]), 0.0, "fallback")

        # Expand with lightweight semantic synonyms (role-ish matching), but stay generic.
        candidates = _expand_semantic_terms(req_norm)

        best_col = ""
        best_score = -1.0
        best_strategy = "fuzzy"

        for col in df.columns:
            col_name = str(col)
            col_norm = normalize_column_name(col_name)
            if not col_norm:
                continue
            if col_norm == req_norm:
                return ResolvedField(requested_field, col_name, 1.0, "exact")

            # Score against requested and its semantic expansions.
            score = -1.0
            strategy = "fuzzy"
            for cand in candidates:
                if cand == col_norm:
                    score = max(score, 0.98)
                    strategy = "semantic_exact"
                    continue
                if cand in col_norm or col_norm in cand:
                    score = max(score, 0.92)
                    strategy = "substring"
                    continue
                score = max(score, SequenceMatcher(None, cand, col_norm).ratio())
            if score > best_score:
                best_col = col_name
                best_score = float(score)
                best_strategy = strategy

        if not best_col:
            best_col = str(df.columns[0])
            best_score = 0.0
            best_strategy = "fallback"
        return ResolvedField(requested_field, best_col, round(best_score, 3), best_strategy)

    def _condition_mask(
        self,
        df: pd.DataFrame,
        column: str,
        operator: str,
        value: object,
        value_to: object,
    ) -> pd.Series:
        series = df[column]

        if operator == "is_empty":
            as_text = series.map(lambda v: "" if pd.isna(v) else str(v).strip())
            return series.isna() | (as_text == "")
        if operator == "is_not_empty":
            as_text = series.map(lambda v: "" if pd.isna(v) else str(v).strip())
            return (~series.isna()) & (as_text != "")

        # Prefer numeric/date comparisons when operator implies ordering.
        if operator in _ORDERING_OPS:
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.notna().mean() >= 0.6:
                left = numeric
                v1 = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                # Fallback: if value is a date-like string ("2004-01-01") on a year column,
                # extract the year so "Doğum Yılı >= 2004" still works.
                if pd.isna(v1) and isinstance(value, str):
                    m = re.search(r"\b(19|20)\d{2}\b", value)
                    if m:
                        v1 = float(m.group(0))
                v2 = pd.to_numeric(pd.Series([value_to]), errors="coerce").iloc[0] if value_to is not None else None
                if pd.isna(v2) and isinstance(value_to, str):
                    m2 = re.search(r"\b(19|20)\d{2}\b", value_to)
                    if m2:
                        v2 = float(m2.group(0))
                return _numeric_mask(left, operator, v1, v2)

            parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
            if parsed.notna().mean() >= 0.6:
                left = parsed
                v1 = pd.to_datetime(value, errors="coerce", dayfirst=True)
                v2 = pd.to_datetime(value_to, errors="coerce", dayfirst=True) if value_to is not None else pd.NaT
                return _datetime_mask(left, operator, v1, v2)

        # Text comparisons (case-insensitive, TR tolerant) via normalize_column_name.
        normalized = series.map(self._normalize_text)
        value_norm = self._normalize_text("" if value is None else value)

        if operator == "equals":
            return normalized == value_norm
        if operator == "not_equals":
            return normalized != value_norm
        if operator == "contains":
            return normalized.str.contains(value_norm, regex=False, na=False)
        if operator == "not_contains":
            return ~normalized.str.contains(value_norm, regex=False, na=False)
        if operator == "starts_with":
            return normalized.str.startswith(value_norm, na=False)
        if operator == "ends_with":
            return normalized.str.endswith(value_norm, na=False)
        if operator in {"in", "not_in"}:
            values = _parse_list_value(value)
            values_norm = {self._normalize_text(v) for v in values}
            mask = normalized.isin(values_norm)
            return ~mask if operator == "not_in" else mask

        raise InvalidInputError(f"Unsupported operator: {operator}")

    def _any_field_mask(
        self,
        df: pd.DataFrame,
        text_columns: list[str],
        operator: str,
        value: object,
        value_to: object,
    ) -> pd.Series:
        # For row-level search, we intentionally only consider text-ish columns.
        # This helps "Sabanci ve IK gorusmesi" match terms that appear in different columns.
        if operator in _ORDERING_OPS:
            raise InvalidInputError("any-field search does not support ordering operators.")

        if not text_columns:
            # No text columns: nothing can match for text operators.
            if operator == "is_empty":
                return pd.Series(False, index=df.index)
            if operator == "is_not_empty":
                return pd.Series(False, index=df.index)
            return pd.Series(False, index=df.index)

        if operator in {"is_empty", "is_not_empty"}:
            # Interpret as: any of the text columns is empty / not empty.
            out = pd.Series(False, index=df.index)
            for col in text_columns:
                series = df[col]
                as_text = series.map(lambda v: "" if pd.isna(v) else str(v).strip())
                col_mask = series.isna() | (as_text == "")
                out |= col_mask if operator == "is_empty" else ~col_mask
            return out

        value_norm = self._normalize_text("" if value is None else value)
        values_norm: set[str] | None = None
        if operator in {"in", "not_in"}:
            values = _parse_list_value(value)
            values_norm = {self._normalize_text(v) for v in values}

        out = pd.Series(False, index=df.index)
        for col in text_columns:
            normalized = df[col].map(self._normalize_text)
            if operator == "equals":
                col_mask = normalized == value_norm
            elif operator == "not_equals":
                col_mask = normalized != value_norm
            elif operator == "contains":
                col_mask = normalized.str.contains(value_norm, regex=False, na=False)
            elif operator == "not_contains":
                col_mask = ~normalized.str.contains(value_norm, regex=False, na=False)
            elif operator == "starts_with":
                col_mask = normalized.str.startswith(value_norm, na=False)
            elif operator == "ends_with":
                col_mask = normalized.str.endswith(value_norm, na=False)
            elif operator in {"in", "not_in"}:
                assert values_norm is not None
                col_mask = normalized.isin(values_norm)
                if operator == "not_in":
                    col_mask = ~col_mask
            else:
                raise InvalidInputError(f"Unsupported operator for any-field search: {operator}")
            out |= col_mask
        return out

    def _build_zero_result_diagnostic(
        self,
        df: pd.DataFrame,
        applied_conditions: list[dict[str, Any]],
        per_condition_counts: list[int],
        logic: str,
    ) -> dict:
        """When matched_count=0, give the agent enough info to self-correct in one round-trip."""
        per_condition_report = []
        suggestions: list[str] = []
        for cond, alone in zip(applied_conditions, per_condition_counts):
            field_name = cond.get("resolved_field") or "*"
            op = cond.get("operator", "")
            val = cond.get("value")
            entry: dict[str, Any] = {
                "field": cond.get("field"),
                "resolved_field": field_name,
                "operator": op,
                "value": val,
                "alone_count": int(alone),
            }
            if field_name and field_name != "*" and field_name in df.columns:
                series = df[field_name]
                top = (
                    series.map(lambda v: "(empty)" if pd.isna(v) or str(v).strip() == "" else str(v).strip())
                    .value_counts()
                    .head(10)
                )
                entry["column_top_values"] = [
                    {"value": str(k), "count": int(v)} for k, v in top.items()
                ]
                # Suggest closest fuzzy match for text equals/contains conditions that returned 0.
                if alone == 0 and op in {"equals", "contains", "starts_with", "ends_with"} and isinstance(val, str):
                    val_norm = self._normalize_text(val)
                    best, best_score = "", 0.0
                    for candidate in top.index:
                        cand_norm = self._normalize_text(str(candidate))
                        if not cand_norm:
                            continue
                        if val_norm in cand_norm or cand_norm in val_norm:
                            score = 0.95
                        else:
                            score = SequenceMatcher(None, val_norm, cand_norm).ratio()
                        if score > best_score:
                            best, best_score = str(candidate), score
                    if best and best_score >= 0.55:
                        entry["suggested_value"] = best
                        entry["suggested_operator"] = "contains"
                        suggestions.append(
                            f"'{val}' kolon '{field_name}' ile eşleşmedi (alone_count=0). "
                            f"En yakın değer: '{best}' (skor={round(best_score, 2)}). "
                            f"contains operatörüyle '{best}' veya '{val}' dene."
                        )
                    elif best:
                        suggestions.append(
                            f"'{val}' kolon '{field_name}' ile eşleşmedi. "
                            f"Mevcut değerlerden bazıları: {', '.join(str(k) for k in top.index[:5])}. "
                            f"Kullanıcıya hangi değeri istediğini sor veya contains operatörüne düş."
                        )
            per_condition_report.append(entry)

        # Suggest dropping the most-restrictive condition for AND queries.
        if logic == "AND" and len(per_condition_counts) > 1 and any(c == 0 for c in per_condition_counts):
            zero_idx = [i for i, c in enumerate(per_condition_counts) if c == 0]
            for idx in zero_idx:
                cond = applied_conditions[idx]
                suggestions.append(
                    f"AND zincirinde koşul #{idx + 1} ({cond.get('resolved_field')}={cond.get('value')}) "
                    f"tek başına 0 satır tutuyor — bu koşul filtreyi sıfırlıyor. "
                    f"Düzelt veya bu koşulu kaldır."
                )
        elif logic == "AND" and all(c > 0 for c in per_condition_counts):
            suggestions.append(
                "Her koşul tek başına satır tutuyor ama AND birleşiminde örtüşme yok. "
                "Veride bu kombinasyon olmayabilir — kullanıcıya bilgi ver, gevşetme veya farklı kombinasyon öner."
            )

        return {
            "logic": logic,
            "per_condition_report": per_condition_report,
            "suggestions": suggestions,
        }

    @staticmethod
    def _summary(matched_df: pd.DataFrame, resolutions: list[ResolvedField]) -> dict:
        # Lightweight distribution on resolved fields (top values) without dumping raw rows.
        fields = [item.resolved for item in resolutions if item.resolved in matched_df.columns and item.resolved != "*"]
        summary: dict[str, Any] = {"top_values": {}}
        for col in list(dict.fromkeys(fields))[:5]:
            counts = (
                matched_df[col]
                .map(lambda item: "(empty)" if pd.isna(item) or str(item).strip() == "" else str(item).strip())
                .value_counts()
                .head(20)
            )
            summary["top_values"][col] = [{"value": str(k), "count": int(v)} for k, v in counts.items()]
        summary["matched_count"] = int(len(matched_df))
        return summary

    @staticmethod
    def _infer_structured_query(natural_query: str) -> dict | None:
        text = str(natural_query or "").strip()
        if not text:
            return None

        norm = normalize_column_name(text)

        # Default is AND. If the user explicitly uses OR wording, switch to OR.
        logic = "AND"
        if any(token in f" {norm} " for token in (" veya ", " or ")):
            logic = "OR"

        return_mode = "sample"
        if any(token in norm for token in ("kac", "say", "count", "how many", "ne kadar")):
            return_mode = "count"
        if any(token in norm for token in ("export", "disari aktar", "disa aktar", "indir", "download")):
            return_mode = "export"

        # Remove intent/command words so the remaining terms are searchable.
        cleanup = f" {norm} "
        for phrase in (
            "kac tane",
            "kac",
            "say",
            "sayisi",
            "count",
            "how many",
            "ne kadar",
            "listele",
            "bul",
            "getir",
            "goster",
            "göster",
            "export",
            "disari aktar",
            "disa aktar",
            "indir",
            "download",
            "adaylar",
            "adayi",
            "aday",
            "kayit",
            "kayitlar",
            "kayitlari",
        ):
            cleanup = cleanup.replace(f" {phrase} ", " ")
        cleanup = " ".join(cleanup.split())

        # Split: "X ve Y" / "X or Y" etc.
        parts = [part.strip() for part in _split_logic(cleanup)]
        parts = [part for part in parts if part]

        # Heuristics:
        # - "email eksik" / "mail yok" -> is_empty on the most likely email column.
        # - Lightweight date/year comparisons (e.g. "2002 sonrasi dogumlular", "2024 oncesi kayitlar")
        #   are supported via field guesses ("dogum tarihi"/"tarih") and ordering operators.
        # - Complex ranges like "tarih 2025-01-01 ile 2025-02-01 arasi" are still best expressed as structured queries.
        conditions: list[dict[str, Any]] = []
        for part in parts[:6]:
            if ":" in part:
                field, val = part.split(":", 1)
                conditions.append({"field": field.strip(), "operator": "contains", "value": val.strip()})
                continue

            # Date/year heuristic:
            # Examples:
            # - "2002 sonrasi dogumlular" -> dogum tarihi >= 2003-01-01
            # - "2002 ve sonrasi dogumlular" -> dogum tarihi >= 2002-01-01
            # - "2024 oncesi" -> tarih <= 2023-12-31 (coarse year cut)
            # School pattern: "X universiteli/universitesi/liseli/lisesi/mezunu/mezunlari" → okul contains X
            school_match = re.match(
                r"^(.+?)\s+(universiteli|universitesi|liseli|lisesi|mezunu|mezunlari)$",
                part.strip(),
            )
            if school_match:
                name = school_match.group(1).strip()
                if name:
                    conditions.append({"field": "okul", "operator": "contains", "value": name})
                    continue

            # Department pattern: "X muhendisligi" / "X bolumu" / "X okuyan" → bolum contains X
            mh_match = re.match(r"^(.+?\s+muhendisligi)\b.*$", part.strip())
            if mh_match:
                name = mh_match.group(1).strip()
                conditions.append({"field": "bolum", "operator": "contains", "value": name})
                continue
            dept_match = re.match(r"^(.+?)\s+(bolumu|bolumunde|bolumunden|okuyan|okuyanlar|ogrenci|ogrencisi|ogrencileri)\s*$", part.strip())
            if dept_match:
                name = dept_match.group(1).strip()
                if name:
                    conditions.append({"field": "bolum", "operator": "contains", "value": name})
                    continue

            # Status / form durumu: "X durumunda" / "X durumunda olan(lar)" / "form durumu X olanlar"
            # MUST come before City to avoid "iletildi durumunda" → city="iletildi durumun"+"da"
            status_match = (
                re.match(r"^(.+?)\s+durumunda(?:\s+olan(?:lar)?)?\s*$", part.strip())
                or re.match(r"^form(?:u)?\s+durumu\s+(.+?)(?:\s+olan(?:lar)?)?\s*$", part.strip())
            )
            if status_match:
                name = status_match.group(1).strip()
                if name:
                    conditions.append({"field": "form durumu", "operator": "contains", "value": name})
                    continue

            # Direct status keywords (without "olan" suffix) — match dummy values: iletildi/iletilmedi/beklemede/hatali email
            stripped = re.sub(r"\s+olan(?:lar)?$", "", part.strip()).strip()
            if stripped in {"iletildi", "iletilmedi", "beklemede", "hatali email", "hatalı email"}:
                conditions.append({"field": "form durumu", "operator": "contains", "value": stripped})
                continue

            # City pattern: "X'da yasayan" / "X ilinde" / "X'li adaylar" / "X sehrinde" / "Xda" → sehir contains X
            city_match = (
                re.match(r"^(.+?)\s+(ilinde|sehrinde|sehrindeki|sehir)\s*$", part.strip())
                or re.match(r"^(.+?)(da|de|ta|te|nda|nde|nta|nte)\s+(yasayan|yasiyan|oturan|ikamet|cali[sş]an|cali[sş]anlar)\s*$", part.strip())
                or re.match(r"^(.+?)(lu|lü|li|lı)\s*(aday|adaylar|kayit|kayitlar|sakin|sakinler)?\s*$", part.strip())
                or re.match(r"^(.+?)(da|de|ta|te|nda|nde|nta|nte)$", part.strip())  # locative-only: "istanbulda"
            )
            if city_match:
                name = city_match.group(1).strip()
                # Reject too-short or non-alpha tokens (skips "kacli", "yili", "lo", numbers)
                if name and len(name) >= 4 and not name.isdigit() and not re.search(r"\d", name):
                    conditions.append({"field": "sehir", "operator": "contains", "value": name})
                    continue

            year_match = re.search(r"\b(19|20)\d{2}\b", part)
            if year_match and any(token in part for token in ("sonra", "sonrasi", "after", "once", "oncesi", "before")):
                year = int(year_match.group(0))
                # Field guess: prefer plain "dogum yili" (year column) when "yil" appears or
                # when the user phrasing is just "X sonrası doğumlular"; fall back to "dogum tarihi"
                # if the user explicitly said "tarih". `_resolve_column` will fuzzy-match.
                if any(t in part for t in ("yil", "year")):
                    field_guess = "dogum yili"
                elif any(t in part for t in ("dogum", "birth", "born")):
                    field_guess = "dogum yili"
                else:
                    field_guess = "tarih"

                is_after = any(t in part for t in ("sonra", "sonrasi", "after"))
                is_before = any(t in part for t in ("once", "oncesi", "before"))
                inclusive = any(t in part for t in ("dahil", "including", ">=", "<="))

                # Year-only value (works on both numeric and datetime columns thanks to fallback in _condition_mask).
                if is_after:
                    start_year = year if inclusive else (year + 1)
                    conditions.append(
                        {"field": field_guess, "operator": "greater_or_equal", "value": str(start_year)}
                    )
                    continue
                if is_before:
                    end_year = year if inclusive else (year - 1)
                    conditions.append(
                        {"field": field_guess, "operator": "less_or_equal", "value": str(end_year)}
                    )
                    continue

            if any(token in part for token in ("eksik", "bos", "yok", "empty", "missing")):
                # Try to infer a field (email/phone/id) from the phrase; if we cannot, fall back to any-field is_empty.
                field_guess = ""
                if any(t in part for t in ("mail", "email", "e posta", "eposta")):
                    field_guess = "email"
                elif any(t in part for t in ("telefon", "phone", "gsm", "mobile")):
                    field_guess = "phone"
                if field_guess:
                    conditions.append({"field": field_guess, "operator": "is_empty", "value": ""})
                else:
                    conditions.append({"field": "", "operator": "is_empty", "value": ""})
                continue

            # Value-only fallback: search term across all columns. Strip lingering suffixes.
            cleaned = part.strip()
            cleaned = re.sub(r"\s+(okuyan|okuyanlar|ogrenci|ogrencisi|ogrencileri|yasayan|yasiyan|oturan|olan|olanlar|olanlari|adaylar|aday|kayitlar|kayit)$", "", cleaned)
            conditions.append({"field": "", "operator": "contains", "value": cleaned})

        return {"conditions": conditions, "logic": logic, "return_mode": return_mode}


def _split_logic(norm: str) -> list[str]:
    for token in (" ve ", " and ", " veya ", " or "):
        norm = norm.replace(token, "|")
    return [part.strip() for part in norm.split("|")]


def _expand_semantic_terms(req_norm: str) -> list[str]:
    # Keep it small and generic; this is not a domain lock-in.
    groups = [
        ("email", ("email", "e posta", "eposta", "mail")),
        ("status", ("durum", "status", "stage", "phase", "asama", "surec", "process", "form durumu")),
        ("university", ("universite", "university", "school", "okul")),
        ("department", ("departman", "department", "birim", "bolum", "unit", "team", "ekip")),
        ("city", ("sehir", "il", "city", "lokasyon", "yer", "location")),
        ("date", ("tarih", "date", "created at", "updated at", "olusturma", "guncelleme")),
        ("year", ("dogum yili", "yil", "year", "birth year", "dogum tarihi", "birth date")),
        ("id", ("id", "record id", "unique id", "no", "numara", "number", "sicil")),
    ]

    out = [req_norm]
    for _, terms in groups:
        terms_norm = [normalize_column_name(t) for t in terms]
        if any(req_norm == t or req_norm in t or t in req_norm for t in terms_norm):
            out.extend(terms_norm)
    # De-dup keep order.
    return list(dict.fromkeys([t for t in out if t]))


def _parse_list_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


def _numeric_mask(series: pd.Series, operator: str, v1: float, v2: float | None) -> pd.Series:
    if pd.isna(v1):
        raise InvalidInputError("Numeric operator requires a numeric value.")
    if operator == "greater_than":
        return series > v1
    if operator == "less_than":
        return series < v1
    if operator == "greater_or_equal":
        return series >= v1
    if operator == "less_or_equal":
        return series <= v1
    if operator == "between":
        if v2 is None or pd.isna(v2):
            raise InvalidInputError("between requires value_to.")
        low = min(float(v1), float(v2))
        high = max(float(v1), float(v2))
        return series.between(low, high, inclusive="both")
    raise InvalidInputError(f"Unsupported operator: {operator}")


def _datetime_mask(series: pd.Series, operator: str, v1: pd.Timestamp, v2: pd.Timestamp) -> pd.Series:
    if pd.isna(v1):
        raise InvalidInputError("Date operator requires a parseable date value.")
    if operator == "greater_than":
        return series > v1
    if operator == "less_than":
        return series < v1
    if operator == "greater_or_equal":
        return series >= v1
    if operator == "less_or_equal":
        return series <= v1
    if operator == "between":
        if pd.isna(v2):
            raise InvalidInputError("between requires value_to.")
        low = min(v1, v2)
        high = max(v1, v2)
        return series.between(low, high, inclusive="both")
    raise InvalidInputError(f"Unsupported operator: {operator}")


excel_query_service = ExcelQueryService()
