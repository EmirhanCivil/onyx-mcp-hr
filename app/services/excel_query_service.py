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
            "sample_rows": sample_rows,
            "summary": summary,
            "export_path": export_path,
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
                v2 = pd.to_numeric(pd.Series([value_to]), errors="coerce").iloc[0] if value_to is not None else None
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
            year_match = re.search(r"\b(19|20)\d{2}\b", part)
            if year_match and any(token in part for token in ("sonra", "sonrasi", "after", "once", "oncesi", "before")):
                year = int(year_match.group(0))
                field_guess = "dogum tarihi" if any(t in part for t in ("dogum", "doğum", "birth", "born")) else "tarih"

                is_after = any(t in part for t in ("sonra", "sonrasi", "after"))
                is_before = any(t in part for t in ("once", "oncesi", "before"))
                inclusive = any(t in part for t in ("ve", "dahil", "including", ">=", "<="))

                if is_after:
                    # "2002 sonrası" is typically interpreted as 2003+ unless the user signals inclusion.
                    start_year = year if inclusive else (year + 1)
                    conditions.append(
                        {"field": field_guess, "operator": "greater_or_equal", "value": f"{start_year:04d}-01-01"}
                    )
                    continue
                if is_before:
                    # "2002 öncesi" interpreted as <= 2001-12-31 unless inclusion is signaled.
                    end_year = year if inclusive else (year - 1)
                    conditions.append(
                        {"field": field_guess, "operator": "less_or_equal", "value": f"{end_year:04d}-12-31"}
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

            # Value-only fallback: search term across all columns.
            conditions.append({"field": "", "operator": "contains", "value": part.strip()})

        return {"conditions": conditions, "logic": logic, "return_mode": return_mode}


def _split_logic(norm: str) -> list[str]:
    for token in (" ve ", " and ", " veya ", " or "):
        norm = norm.replace(token, "|")
    return [part.strip() for part in norm.split("|")]


def _expand_semantic_terms(req_norm: str) -> list[str]:
    # Keep it small and generic; this is not a domain lock-in.
    groups = [
        ("email", ("email", "e posta", "eposta", "mail")),
        ("status", ("durum", "status", "stage", "phase", "asama", "surec", "process")),
        ("university", ("universite", "university", "school", "okul")),
        ("department", ("departman", "department", "birim", "bolum", "unit", "team", "ekip")),
        ("date", ("tarih", "date", "created at", "updated at", "olusturma", "guncelleme")),
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
