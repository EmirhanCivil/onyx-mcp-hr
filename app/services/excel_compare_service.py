"""Excel comparison and de-duplication service."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from itertools import combinations

import pandas as pd

from app.analyzers.diff_analyzer import _normalize_compare_value, compare_by_key, compare_columns, row_set_difference
from app.analyzers.duplicate_analyzer import deduplicate, find_duplicates
from app.core.file_registry import file_registry
from app.exporters.excel_exporter import export_dataframe, export_multiple_sheets
from app.utils.dataframe_utils import normalize_column_name, safe_preview
from app.utils.validation_utils import parse_columns


class ExcelCompareService:
    """High-level operations for schema diff, row diff, and duplicate cleanup."""

    def compare_schema(self, file_id_a: str, file_id_b: str) -> dict:
        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)
        schema = compare_columns(df_a, df_b)
        schema["semantic_column_matches"] = self._column_mapping(df_a, df_b)
        schema["semantic_match_count"] = len(schema["semantic_column_matches"])
        return schema

    def compare_rows(
        self,
        file_id_a: str,
        file_id_b: str,
        compare_columns_csv: str = "",
        limit: int = 50,
        export: bool = False,
    ) -> dict:
        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)
        columns = parse_columns(compare_columns_csv) or None
        result = row_set_difference(df_a, df_b, columns, limit)
        files: list[str] = []
        if export:
            only_a = self._rows_only(df_a, df_b, columns, side="a")
            only_b = self._rows_only(df_a, df_b, columns, side="b")
            files.append(export_multiple_sheets({"only_in_a": only_a, "only_in_b": only_b}, "row_differences"))
        result["exported_files"] = files
        return result

    def compare_by_key(
        self,
        file_id_a: str,
        file_id_b: str,
        key_columns_csv: str,
        compare_columns_csv: str = "",
        limit: int = 50,
    ) -> dict:
        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)
        keys = parse_columns(key_columns_csv)
        compare_cols = parse_columns(compare_columns_csv) or None
        result = compare_by_key(df_a, df_b, keys, compare_cols, limit)
        result["key_quality"] = self._key_quality(df_a, df_b, keys)
        return result

    def compare_auto(
        self,
        file_id_a: str,
        file_id_b: str,
        key_query: str = "",
        compare_columns_csv: str = "",
        limit: int = 50,
        export: bool = False,
    ) -> dict:
        """Compare two files even when equivalent columns have different labels."""

        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)
        meta_a = file_registry.get_meta(file_id_a)
        meta_b = file_registry.get_meta(file_id_b)
        mapping = self._column_mapping(df_a, df_b)
        if not mapping:
            return {
                "selected_files": {"a": meta_a.__dict__, "b": meta_b.__dict__},
                "schema": compare_columns(df_a, df_b),
                "mapping": [],
                "message": "Eslesebilen kolon bulunamadi; once kolon semasini inceleyin.",
            }

        rename_b = {item["b"]: item["a"] for item in mapping}
        mapped_b = df_b.rename(columns=rename_b)
        mapped_columns = [item["a"] for item in mapping if item["a"] in df_a.columns and item["a"] in mapped_b.columns]
        key_diagnostics = self._infer_key_columns_with_diagnostics(df_a, mapped_b, mapped_columns, key_query)
        key_columns = key_diagnostics.get("key_columns") or []
        requested_compare = parse_columns(compare_columns_csv)
        if requested_compare:
            compare_cols = [self._best_column_from_list(mapped_columns, col) for col in requested_compare]
            compare_cols = [col for col in dict.fromkeys(compare_cols) if col and col not in key_columns]
        else:
            compare_cols = [col for col in mapped_columns if col not in key_columns]

        files: list[str] = []
        if key_columns:
            result = compare_by_key(df_a, mapped_b, key_columns, compare_cols or None, limit)
            mode = "keyed"
            if export:
                sheets: dict[str, pd.DataFrame] = {}
                sheets["Summary"] = pd.DataFrame(
                    [
                        {
                            "mode": mode,
                            "key_columns": ", ".join(key_columns),
                            "key_confidence": key_diagnostics.get("confidence"),
                            "matched_keys": result.get("matched_keys"),
                            "changed_row_count": result.get("changed_row_count"),
                            "only_in_a_count": result.get("only_in_a_count"),
                            "only_in_b_count": result.get("only_in_b_count"),
                        }
                    ]
                )
                delta_df = pd.DataFrame(result.get("delta_view_preview", []))
                if not delta_df.empty:
                    sheets["DeltaView"] = delta_df
                changed_df = pd.DataFrame(result.get("changed_rows_preview", []))
                if not changed_df.empty:
                    sheets["ChangedRows"] = changed_df
                ranked_df = pd.DataFrame(result.get("changed_columns_ranked", []))
                if not ranked_df.empty:
                    sheets["ChangedColumns"] = ranked_df
                only_a_df = pd.DataFrame(result.get("only_in_a_preview", []))
                if not only_a_df.empty:
                    sheets["OnlyInA_Preview"] = only_a_df
                only_b_df = pd.DataFrame(result.get("only_in_b_preview", []))
                if not only_b_df.empty:
                    sheets["OnlyInB_Preview"] = only_b_df
                files.append(export_multiple_sheets(sheets, "auto_compare_report"))
        else:
            result = row_set_difference(df_a, mapped_b, mapped_columns, limit)
            mode = "row_set"
            if export:
                only_a = self._rows_only(df_a, mapped_b, mapped_columns, side="a")
                only_b = self._rows_only(df_a, mapped_b, mapped_columns, side="b")
                files.append(export_multiple_sheets({"only_in_a": only_a, "only_in_b": only_b}, "auto_row_differences"))

        result["selected_files"] = {"a": meta_a.__dict__, "b": meta_b.__dict__}
        result["comparison_mode"] = mode
        result["inferred_key_columns"] = key_columns
        result["key_quality"] = self._key_quality(df_a, mapped_b, key_columns) if key_columns else {
            "status": "fallback",
            "message": "Guvenilir anahtar kolon bulunamadi; normalize edilmis satir fingerprint karsilastirmasi kullanildi.",
        }
        result["key_diagnostics"] = key_diagnostics
        result["mapped_columns"] = mapping
        result["unmapped_columns"] = self._unmapped_columns(df_a, df_b, mapping)
        result["schema"] = compare_columns(df_a, df_b)
        result["structure_summary"] = self._structure_summary(df_a, df_b, mapping)
        result["comparison_summary"] = self._comparison_summary(result, mapping, key_columns)
        result["answer_guidance"] = (
            "Kiyaslama mapped_columns ve inferred_key_columns alanlarina gore yapildi. "
            "changed_rows_preview icindeki changed_columns gercek hucre farklarini gosterir; "
            "delta_view_preview degisen hucreleri kolon bazinda (old/new) listeler; "
            "only_in_a/only_in_b yeni veya kaybolan kayitlari gosterir."
        )
        result["files"] = files
        return result

    def find_duplicates(self, file_id: str, key_columns_csv: str = "", keep: str = "first") -> dict:
        df = file_registry.get_frame(file_id)
        keys = parse_columns(key_columns_csv) or None
        return find_duplicates(df, keys, keep)

    def deduplicate_file(
        self,
        file_id: str,
        key_columns_csv: str = "",
        keep: str = "first",
        export: bool = True,
    ) -> dict:
        df = file_registry.get_frame(file_id)
        keys = parse_columns(key_columns_csv) or None
        cleaned, summary = deduplicate(df, keys, keep)
        registered = file_registry.register(f"deduplicated:{file_id}", cleaned, tags={"source_file_id": file_id})
        files = [export_dataframe(cleaned, "deduplicated_rows")] if export else []
        return {"summary": summary, "new_file": registered.__dict__, "files": files}

    def filter_rows(
        self,
        file_id: str,
        column: str = "",
        value: str = "",
        mode: str = "equals",
        query: str = "",
        limit: int = 50,
        export: bool = False,
    ) -> dict:
        """Filter rows by explicit column/value or infer them from a short Turkish query."""

        df = file_registry.get_frame(file_id)
        inferred = self._infer_filter(df, query) if query and (not column or not value) else {}
        target_column = column or inferred.get("column", "")
        target_value = value or inferred.get("value", "")
        target_mode = (mode or inferred.get("mode") or "equals").strip().lower()
        if not target_column or target_column not in df.columns:
            target_column = self._best_column(df, target_column or query)
        if not target_value:
            target_value = inferred.get("value", "")

        series = df[target_column].map(lambda item: "" if pd.isna(item) else str(item).strip())
        value_norm = normalize_column_name(target_value)
        series_norm = series.map(normalize_column_name)

        if target_mode in {"not_equals", "not", "exclude", "different"}:
            mask = series_norm != value_norm
        elif target_mode in {"contains", "include"}:
            mask = series_norm.str.contains(value_norm, regex=False, na=False)
        elif target_mode in {"not_contains"}:
            mask = ~series_norm.str.contains(value_norm, regex=False, na=False)
        else:
            mask = series_norm == value_norm

        filtered = df[mask].copy()
        files = [export_dataframe(filtered, "filtered_rows")] if export else []
        return {
            "file_id": file_id,
            "filter": {
                "column": target_column,
                "value": target_value,
                "mode": target_mode,
                "query": query,
                "inferred": inferred,
            },
            "matched_rows": int(len(filtered)),
            "total_rows": int(len(df)),
            "preview": safe_preview(filtered, limit),
            "files": files,
        }

    def compare_column_changes(
        self,
        file_id_a: str,
        file_id_b: str,
        key_query: str = "email tc kimlik aday id",
        column_query: str = "form durum iletim",
        from_value: str = "",
        to_value: str = "",
        limit: int = 50,
        export: bool = False,
    ) -> dict:
        """Compare a business status column between two spreadsheets by an inferred key."""

        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)
        mapping = self._column_mapping(df_a, df_b)
        rename_b = {item["b"]: item["a"] for item in mapping}
        mapped_b = df_b.rename(columns=rename_b)
        mapped_columns = [item["a"] for item in mapping if item["a"] in df_a.columns and item["a"] in mapped_b.columns]
        if mapped_columns:
            inferred_keys = self._infer_key_columns(df_a, mapped_b, mapped_columns, key_query)
            key_col = inferred_keys[0] if inferred_keys else self._best_column_from_list(mapped_columns, key_query)
            compare_pool = [col for col in mapped_columns if col != key_col]
            value_col = self._best_column_from_list(compare_pool, column_query)
        else:
            key_col = self._best_common_column(df_a, df_b, key_query)
            value_col = self._best_common_column(df_a, df_b, column_query)

        left = df_a[[key_col, value_col]].copy()
        right = mapped_b[[key_col, value_col]].copy()
        left.columns = [key_col, "value_a"]
        right.columns = [key_col, "value_b"]
        left["_join_key"] = left[key_col].map(_normalize_compare_value)
        right["_join_key"] = right[key_col].map(_normalize_compare_value)
        merged = left.merge(right, on="_join_key", how="outer", suffixes=("_a", "_b"), indicator=True)
        merged["value_a_norm"] = merged["value_a"].map(_normalize_compare_value)
        merged["value_b_norm"] = merged["value_b"].map(_normalize_compare_value)
        changed = merged[merged["value_a_norm"] != merged["value_b_norm"]].copy()

        if from_value:
            changed = changed[changed["value_a_norm"] == _normalize_compare_value(from_value)]
        if to_value:
            changed = changed[changed["value_b_norm"] == _normalize_compare_value(to_value)]

        export_df = changed.drop(columns=["_join_key", "value_a_norm", "value_b_norm"], errors="ignore")
        files = [export_dataframe(export_df, "column_changes")] if export else []
        return {
            "key_column": key_col,
            "compared_column": value_col,
            "mapped_columns": mapping,
            "from_value": from_value,
            "to_value": to_value,
            "changed_rows": int(len(changed)),
            "preview": safe_preview(export_df, limit),
            "files": files,
        }

    def summarize_column(self, file_id: str, column: str = "", query: str = "", limit: int = 30) -> dict:
        from app.services.excel_query_service import excel_query_service

        df = file_registry.get_frame(file_id)

        # If `query` is a natural-language filter (contains operators like "ve", year tokens,
        # locative suffixes, or column hints), apply it as a filter first, then summarize.
        # Otherwise treat `query` as a column-name hint (legacy behavior).
        filtered_df = df
        applied_filter = None
        if query:
            looks_like_filter = bool(
                re.search(r"\b(19|20)\d{2}\b", query)
                or any(t in f" {query.lower()} " for t in (" ve ", " veya ", " and ", " or "))
                or any(t in query.lower() for t in ("li ", "lı ", "lu ", "lü ", "da ", "de ", "ta ", "te ",
                                                      "sonrasi", "oncesi", "yasayan", "ilinde", "sehrinde",
                                                      "muhendisligi", "bolumu", "okuyan", "mezunu",
                                                      "durumunda", "iletildi", "iletilmedi", "beklemede"))
            )
            if looks_like_filter:
                try:
                    res = excel_query_service.query_rows(file_id, natural_query=query, return_mode="count")
                    # Re-apply filter to get filtered DataFrame
                    structured = excel_query_service._infer_structured_query(query)
                    if structured and structured.get("conditions"):
                        # Reuse query_rows with full mode to extract filtered df
                        from app.core.exceptions import InvalidInputError  # noqa
                        masks = []
                        for cond in res["data"]["conditions_applied"]:
                            field = cond.get("resolved_field") or "*"
                            op = cond["operator"]
                            v = cond["value"]
                            v2 = cond.get("value_to")
                            if field == "*":
                                text_cols = [c for c in df.columns if df[c].dtype == object]
                                masks.append(excel_query_service._any_field_mask(df, text_cols, op, v, v2))
                            else:
                                masks.append(excel_query_service._condition_mask(df, field, op, v, v2))
                        if masks:
                            mask = masks[0]
                            for m in masks[1:]:
                                mask = (mask & m) if str(res["data"]["logic"]).upper() == "AND" else (mask | m)
                            filtered_df = df[mask].copy()
                            applied_filter = {
                                "natural_query": query,
                                "logic": res["data"]["logic"],
                                "conditions": res["data"]["conditions_applied"],
                                "matched_count": int(mask.sum()),
                            }
                except Exception:
                    filtered_df = df

        # Resolve target column(s): allow comma-separated list
        col_input = column.strip()
        if "," in col_input:
            requested = [c.strip() for c in col_input.split(",") if c.strip()]
        elif col_input:
            requested = [col_input]
        else:
            requested = [self._best_column(df, query or "")]

        per_column: list[dict] = []
        for req in requested:
            target = req if req in filtered_df.columns else self._best_column(filtered_df, req)
            counts = (
                filtered_df[target]
                .map(lambda item: "(empty)" if pd.isna(item) or str(item).strip() == "" else str(item).strip())
                .value_counts()
                .head(limit)
            )
            total = int(len(filtered_df))
            per_column.append({
                "column": target,
                "requested": req,
                "total_rows": total,
                "distinct_values": int(filtered_df[target].nunique(dropna=False)),
                "top_values": [
                    {
                        "value": str(idx),
                        "count": int(val),
                        "percent": round(100 * float(val) / total, 1) if total else 0.0,
                    }
                    for idx, val in counts.items()
                ],
            })

        result: dict = {
            "file_id": file_id,
            "scope_total_rows": int(len(filtered_df)),
            "source_total_rows": int(len(df)),
            "applied_filter": applied_filter,
            "columns": per_column,
        }
        # Backward-compat: if single column requested, also expose top-level fields the old callers rely on.
        if len(per_column) == 1:
            first = per_column[0]
            result.update({
                "column": first["column"],
                "total_rows": first["total_rows"],
                "distinct_values": first["distinct_values"],
                "top_values": first["top_values"],
            })
        return result

    def find_missing_in_target(
        self,
        source_file_id: str = "",
        target_file_id: str = "",
        key_columns: str = "Email",
        source_filter_query: str = "",
        source_structured_query: dict | None = None,
        source_file_query: str = "",
        target_file_query: str = "",
        sample_limit: int = 20,
        export: bool = True,
    ) -> dict:
        """Source'a filtre uygula, sonra Target'ta key_columns ile eşleşmeyen satırları döndür.
        Use case: 'Filtreden geçen adaylardan, anket iletilenler listesinde olmayanları bul.'
        file_id verilmezse file_query ile dosyayı isimden çöz."""
        from app.services.excel_query_service import excel_query_service
        from app.exporters.excel_exporter import export_dataframe
        from app.services.excel_service import excel_service as _excel_service

        source_file_id = source_file_id or self._resolve_file(source_file_query, _excel_service)
        target_file_id = target_file_id or self._resolve_file(target_file_query, _excel_service)
        if not source_file_id or not target_file_id:
            raise ValueError(
                "source_file_id veya source_file_query, target_file_id veya target_file_query verilmeli."
            )

        source = file_registry.get_frame(source_file_id)
        target = file_registry.get_frame(target_file_id)

        # 1. Resolve key columns in both files (fuzzy)
        key_hints = [k.strip() for k in str(key_columns or "").split(",") if k.strip()]
        if not key_hints:
            raise ValueError("key_columns boş olamaz — örn 'Email' veya 'Ad Soyad,Email'")
        source_keys: list[str] = []
        target_keys: list[str] = []
        for hint in key_hints:
            sk = hint if hint in source.columns else self._best_column(source, hint)
            tk = hint if hint in target.columns else self._best_column(target, hint)
            source_keys.append(sk)
            target_keys.append(tk)

        # 2. Apply filter to source if provided
        warnings: list[str] = []
        if source_structured_query or source_filter_query:
            mask = self._build_filter_mask(
                source, source_structured_query, source_filter_query, excel_query_service
            )
            filtered_source = source[mask].copy()
            applied_filter_summary = {
                "source_natural_query": source_filter_query,
                "source_structured_query": source_structured_query,
                "filtered_count": int(len(filtered_source)),
            }
        else:
            filtered_source = source.copy()
            applied_filter_summary = None

        # 3. Build target key set (normalized for case/TR-tolerance)
        target_key_set = set()
        for row in target[target_keys].itertuples(index=False):
            target_key_set.add(tuple(_normalize_compare_value(v) for v in row))

        # 4. Anti-join: source rows whose key tuple NOT in target
        def _src_key(row) -> tuple:
            return tuple(_normalize_compare_value(row[c]) for c in source_keys)

        if len(filtered_source):
            keys_series = filtered_source.apply(_src_key, axis=1)
            in_target_mask = keys_series.map(lambda k: k in target_key_set)
        else:
            in_target_mask = pd.Series([], dtype=bool)
        missing_df = filtered_source[~in_target_mask].copy()
        matched_df = filtered_source[in_target_mask].copy()

        # 5. Export missing as xlsx
        files: list[str] = []
        outputs: list[dict] = []
        export_path: str | None = None
        if export and len(missing_df):
            export_path = export_dataframe(missing_df, "candidates_missing_in_target")
            files.append(export_path)
            outputs.append({
                "type": "file",
                "title": "candidates_missing_in_target.xlsx",
                "description": "Filtre kümesinde olup target dosyasında bulunmayan kayıtlar.",
                "format": "xlsx",
                "path": export_path,
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "display": True,
            })

        return {
            "source_file_id": source_file_id,
            "target_file_id": target_file_id,
            "source_keys": source_keys,
            "target_keys": target_keys,
            "source_total": int(len(source)),
            "source_filtered_count": int(len(filtered_source)),
            "target_total": int(len(target)),
            "in_target_count": int(len(matched_df)),
            "missing_count": int(len(missing_df)),
            "missing_sample": safe_preview(missing_df, sample_limit),
            "applied_filter": applied_filter_summary,
            "files": files,
            "generated_outputs": outputs,
            "warnings": warnings,
        }

    @staticmethod
    def _resolve_file(file_query: str, excel_svc) -> str:
        """Dosya adı/query'den file_id çıkar — yoksa boş string döner."""
        if not file_query:
            return ""
        try:
            excel_svc.scan_uploads()
        except Exception:
            pass
        selected = excel_svc.select_file(file_query, "")
        if selected and "file_id" in selected:
            return selected["file_id"]
        return ""

    def _build_filter_mask(
        self,
        df: pd.DataFrame,
        structured_query: dict | None,
        natural_query: str,
        query_svc,
    ) -> pd.Series:
        """Build a pandas boolean mask using query_service's parser + condition mask helpers."""
        query = structured_query or query_svc._infer_structured_query(natural_query) or {}
        conditions = query.get("conditions") or []
        logic = str(query.get("logic") or "AND").strip().upper()
        if not conditions:
            return pd.Series(True, index=df.index)

        masks: list[pd.Series] = []
        text_cols = [str(c) for c in df.columns if df[c].dtype == object]
        for cond in conditions:
            field = str(cond.get("field") or "").strip()
            operator = str(cond.get("operator") or "").strip().lower()
            value = cond.get("value")
            value_to = cond.get("value_to")
            if not field:
                masks.append(query_svc._any_field_mask(df, text_cols, operator, value, value_to))
                continue
            resolved = field if field in df.columns else query_svc._resolve_column(df, field).resolved
            masks.append(query_svc._condition_mask(df, resolved, operator, value, value_to))
        if logic == "OR":
            final = pd.Series(False, index=df.index)
            for m in masks:
                final |= m
        else:
            final = pd.Series(True, index=df.index)
            for m in masks:
                final &= m
        return final

    @staticmethod
    def _rows_only(df_a: pd.DataFrame, df_b: pd.DataFrame, columns: list[str] | None, side: str) -> pd.DataFrame:
        cols = columns or [c for c in df_a.columns if c in df_b.columns]
        left = df_a if side == "a" else df_b
        right = df_b if side == "a" else df_a
        left_norm = left[cols].copy()
        right_norm = right[cols].copy()
        for col in cols:
            left_norm[col] = left_norm[col].map(_normalize_compare_value)
            right_norm[col] = right_norm[col].map(_normalize_compare_value)
        right_keys = set(map(tuple, right_norm.to_numpy()))
        mask = ~left_norm.apply(tuple, axis=1).isin(right_keys)
        return left[mask].copy()

    @staticmethod
    def _best_column(df: pd.DataFrame, hint: str) -> str:
        normalized_hint = normalize_column_name(hint)
        scored: list[tuple[int, str]] = []
        for column in df.columns:
            normalized = normalize_column_name(column)
            score = 0
            for token in normalized_hint.split():
                if token and token in normalized:
                    score += len(token)
            if normalized in normalized_hint:
                score += len(normalized)
            scored.append((score, str(column)))
        scored.sort(reverse=True)
        if scored and scored[0][0] > 0:
            return scored[0][1]
        return str(df.columns[0])

    def _best_common_column(self, df_a: pd.DataFrame, df_b: pd.DataFrame, hint: str) -> str:
        common = [column for column in df_a.columns if column in df_b.columns]
        if not common:
            return self._best_column(df_a, hint)
        temp = pd.DataFrame(columns=common)
        return self._best_column(temp, hint)

    def _infer_filter(self, df: pd.DataFrame, query: str) -> dict:
        normalized_query = normalize_column_name(query)
        best = {"column": self._best_column(df, normalized_query), "value": "", "mode": "equals", "score": 0}
        best_score = 0
        for column in df.columns:
            column_score = 0
            normalized_column = normalize_column_name(column)
            for token in normalized_query.split():
                if token and token in normalized_column:
                    column_score += len(token)

            values = (
                df[column]
                .dropna()
                .astype(str)
                .map(str.strip)
                .drop_duplicates()
                .head(500)
                .tolist()
            )
            for value in values:
                normalized_value = normalize_column_name(value)
                value_score = 0
                if normalized_value and normalized_value in normalized_query:
                    value_score += len(normalized_value) + 30
                for token in normalized_value.split():
                    if token and token in normalized_query:
                        value_score += len(token)
                score = column_score + value_score
                if score > best_score:
                    best = {"column": str(column), "value": value, "mode": "equals", "score": score}
                    best_score = score
        return best

    def _column_mapping(self, df_a: pd.DataFrame, df_b: pd.DataFrame) -> list[dict]:
        candidates: list[dict] = []
        for col_a in df_a.columns:
            for col_b in df_b.columns:
                score, signals = self._column_match_score(df_a, df_b, str(col_a), str(col_b))
                if score >= 0.62:
                    candidates.append({
                        "a": str(col_a),
                        "b": str(col_b),
                        "confidence": round(float(score), 3),
                        **signals,
                    })

        mapped = []
        used_a = set()
        used_b = set()
        for candidate in sorted(candidates, key=lambda item: item["confidence"], reverse=True):
            if candidate["a"] in used_a or candidate["b"] in used_b:
                continue
            used_a.add(candidate["a"])
            used_b.add(candidate["b"])
            mapped.append(candidate)
        return mapped

    def _infer_key_columns(self, df_a: pd.DataFrame, df_b: pd.DataFrame, columns: list[str], key_query: str) -> list[str]:
        query_norm = normalize_column_name(key_query)
        query_canonical = self._canonical_column(key_query) if key_query else ""
        scored: list[tuple[float, str, dict]] = []
        for column in columns:
            norm = normalize_column_name(column)
            canonical = self._canonical_column(column)
            stats = self._key_stats(df_a, df_b, column)
            score = (
                self._key_identity_weight(canonical)
                + stats["unique_avg"] * 1.2
                + stats["non_null_avg"] * 0.5
                + stats["overlap"] * 1.2
            )
            if query_canonical and query_canonical == canonical:
                score += 1.5
            for token in query_norm.split():
                if token and token in norm:
                    score += 1.0
            scored.append((score, column, stats))
        scored.sort(reverse=True)
        if scored:
            top_score, top_column, top_stats = scored[0]
            top_canonical = self._canonical_column(top_column)
            identity_weight = self._key_identity_weight(top_canonical)
            if (
                top_score >= 2.1
                and top_stats["non_null_avg"] >= 0.65
                and top_stats["unique_avg"] >= 0.55
                and (top_stats["overlap"] >= 0.25 or identity_weight >= 1.6)
                and self._can_use_single_key(identity_weight, top_stats, max(len(df_a), len(df_b)))
                and not self._is_volatile_column(top_canonical)
            ):
                return [top_column]

        composite = self._infer_composite_key(df_a, df_b, scored)
        if composite:
            return composite
        return []

    def _infer_key_columns_with_diagnostics(self, df_a: pd.DataFrame, df_b: pd.DataFrame, columns: list[str], key_query: str) -> dict:
        """Pick key columns and return diagnostics to help agents avoid wrong keys."""

        query_norm = normalize_column_name(key_query)
        query_canonical = self._canonical_column(key_query) if key_query else ""
        candidates: list[dict] = []
        for column in columns:
            norm = normalize_column_name(column)
            canonical = self._canonical_column(column)
            stats = self._key_stats(df_a, df_b, column)
            score = (
                self._key_identity_weight(canonical)
                + stats["unique_avg"] * 1.2
                + stats["non_null_avg"] * 0.5
                + stats["overlap"] * 1.2
            )
            if query_canonical and query_canonical == canonical:
                score += 1.5
            for token in query_norm.split():
                if token and token in norm:
                    score += 1.0
            candidates.append(
                {
                    "column": column,
                    "canonical": canonical,
                    "score": round(float(score), 4),
                    "stats": {k: round(float(v), 4) for k, v in stats.items()},
                    "identity_weight": round(float(self._key_identity_weight(canonical)), 3),
                }
            )
        candidates.sort(key=lambda x: x["score"], reverse=True)

        selected = self._infer_key_columns(df_a, df_b, columns, key_query)

        confidence = 0.0
        reason = ""
        warnings: list[str] = []
        if selected and candidates:
            top = candidates[0]
            second = candidates[1] if len(candidates) > 1 else None
            margin = float(top["score"] - (second["score"] if second else 0.0))
            overlap = float(top["stats"].get("overlap", 0.0))
            uniq = float(top["stats"].get("unique_avg", 0.0))
            nn = float(top["stats"].get("non_null_avg", 0.0))

            confidence = min(
                1.0,
                max(
                    0.0,
                    (0.45 * overlap) + (0.25 * uniq) + (0.15 * nn) + (0.15 * min(1.0, margin / 2.0)),
                ),
            )
            reason = f"top={top['column']} overlap={overlap:.2f} unique={uniq:.2f} non_null={nn:.2f} margin={margin:.2f}"

            if top["canonical"] == "name" and overlap < 0.35:
                warnings.append("Anahtar kolon isim gibi gorunuyor ve iki dosya arasinda ortaklik dusuk; email/id gibi daha saglam bir anahtar gerekebilir.")
            if overlap < 0.2 and top["identity_weight"] < 1.6:
                warnings.append("Anahtar kolon overlap dusuk; sonuc kismi eslesme olabilir. key_query ile anahtari netlestirin.")
        else:
            warnings.append("Anahtar kolon otomatik tespit edilemedi; key_query ile anahtari belirtin (ornek: id/email/telefon).")

        return {
            "key_columns": selected,
            "confidence": round(float(confidence), 4),
            "reason": reason,
            "candidates": candidates[:10],
            "warnings": warnings,
        }

    def _best_column_from_list(self, columns: list[str], hint: str) -> str:
        hint_norm = normalize_column_name(hint)
        hint_canonical = self._canonical_column(hint) if hint else ""
        scored = []
        for column in columns:
            norm = normalize_column_name(column)
            score = SequenceMatcher(None, hint_norm, norm).ratio()
            if hint_norm in norm or norm in hint_norm:
                score += 0.5
            if hint_canonical and hint_canonical == self._canonical_column(column):
                score += 1.2
            scored.append((score, column))
        scored.sort(reverse=True)
        return scored[0][1] if scored else ""

    def _column_match_score(self, df_a: pd.DataFrame, df_b: pd.DataFrame, col_a: str, col_b: str) -> tuple[float, dict]:
        norm_a = normalize_column_name(col_a)
        norm_b = normalize_column_name(col_b)
        canon_a = self._canonical_column(col_a)
        canon_b = self._canonical_column(col_b)
        name_similarity = max(SequenceMatcher(None, norm_a, norm_b).ratio(), self._token_similarity(norm_a, norm_b))
        if norm_a and norm_b and (norm_a in norm_b or norm_b in norm_a):
            name_similarity = max(name_similarity, 0.86)
        value_overlap = self._value_overlap(df_a[col_a], df_b[col_b])
        type_score = self._type_compatibility(df_a[col_a], df_b[col_b])

        if str(col_a) == str(col_b) or norm_a == norm_b:
            score = 1.0
            strategy = "exact_header"
        elif canon_a == canon_b and self._is_known_canonical(canon_a):
            score = max(0.93, 0.86 + (value_overlap * 0.08) + (type_score * 0.04))
            strategy = "semantic_alias"
        else:
            score = (name_similarity * 0.68) + (value_overlap * 0.24) + (type_score * 0.08)
            if value_overlap >= 0.75 and name_similarity >= 0.28:
                score = max(score, 0.82)
            elif value_overlap >= 0.55 and name_similarity >= 0.40:
                score = max(score, 0.74)
            strategy = "fuzzy_header_value"

        return score, {
            "canonical": canon_a if canon_a == canon_b else "",
            "strategy": strategy,
            "name_similarity": round(float(name_similarity), 3),
            "value_overlap": round(float(value_overlap), 3),
        }

    @staticmethod
    def _token_similarity(left: str, right: str) -> float:
        left_tokens = {token for token in left.split() if token}
        right_tokens = {token for token in right.split() if token}
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens)
        return overlap / max(len(left_tokens), len(right_tokens))

    @staticmethod
    def _type_compatibility(left: pd.Series, right: pd.Series) -> float:
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            return 1.0
        if pd.api.types.is_datetime64_any_dtype(left) and pd.api.types.is_datetime64_any_dtype(right):
            return 1.0
        if pd.api.types.is_object_dtype(left) and pd.api.types.is_object_dtype(right):
            return 0.85
        return 0.35

    def _value_overlap(self, left: pd.Series, right: pd.Series) -> float:
        left_values = self._normalized_value_set(left)
        right_values = self._normalized_value_set(right)
        if not left_values or not right_values:
            return 0.0
        intersection = len(left_values & right_values)
        coverage = intersection / max(min(len(left_values), len(right_values)), 1)
        jaccard = intersection / max(len(left_values | right_values), 1)
        score = max(coverage, jaccard)
        if min(len(left_values), len(right_values)) <= 3:
            score *= 0.55
        return float(score)

    @staticmethod
    def _normalized_value_set(series: pd.Series, limit: int = 1000) -> set[str]:
        values = []
        for value in series.dropna().head(limit).tolist():
            normalized = _normalize_compare_value(value)
            if normalized:
                values.append(normalized)
        return set(values)

    def _key_stats(self, df_a: pd.DataFrame, df_b: pd.DataFrame, column: str) -> dict:
        a_values = df_a[column].map(_normalize_compare_value)
        b_values = df_b[column].map(_normalize_compare_value)
        a_non_empty = a_values[a_values != ""]
        b_non_empty = b_values[b_values != ""]
        a_set = set(a_non_empty.tolist())
        b_set = set(b_non_empty.tolist())
        intersection = len(a_set & b_set)
        overlap = intersection / max(min(len(a_set), len(b_set)), 1) if a_set and b_set else 0.0
        return {
            "non_null_avg": float(((a_values != "").mean() + (b_values != "").mean()) / 2),
            "unique_avg": float((a_non_empty.nunique() / max(len(df_a), 1) + b_non_empty.nunique() / max(len(df_b), 1)) / 2),
            "overlap": float(overlap),
        }

    def _infer_composite_key(self, df_a: pd.DataFrame, df_b: pd.DataFrame, scored: list[tuple[float, str, dict]]) -> list[str]:
        candidates = [
            column for score, column, stats in scored[:6]
            if score >= 1.0
            and stats["non_null_avg"] >= 0.65
            and (self._key_identity_weight(self._canonical_column(column)) >= 0.8 or max(len(df_a), len(df_b)) >= 8)
            and not self._is_volatile_column(self._canonical_column(column))
        ]
        for size in (2, 3):
            for combo in combinations(candidates, size):
                stats = self._tuple_key_stats(df_a, df_b, list(combo))
                if stats["unique_avg"] >= 0.80 and stats["overlap"] >= 0.25:
                    return list(combo)
        return []

    @staticmethod
    def _tuple_key_stats(df_a: pd.DataFrame, df_b: pd.DataFrame, columns: list[str]) -> dict:
        def tuples(df: pd.DataFrame) -> list[tuple[str, ...]]:
            normalized = df[columns].copy()
            for col in normalized.columns:
                normalized[col] = normalized[col].map(_normalize_compare_value)
            return [tuple(row) for row in normalized.to_numpy() if any(row)]

        a_tuples = tuples(df_a)
        b_tuples = tuples(df_b)
        a_set = set(a_tuples)
        b_set = set(b_tuples)
        intersection = len(a_set & b_set)
        overlap = intersection / max(min(len(a_set), len(b_set)), 1) if a_set and b_set else 0.0
        return {
            "unique_avg": float((len(a_set) / max(len(df_a), 1) + len(b_set) / max(len(df_b), 1)) / 2),
            "overlap": float(overlap),
        }

    @staticmethod
    def _key_identity_weight(canonical: str) -> float:
        weights = {
            "record_id": 2.6,
            "unique_id": 2.6,
            "email": 2.4,
            "candidate_id": 2.3,
            "customer_id": 2.3,
            "product_id": 2.3,
            "order_id": 2.3,
            "transaction_id": 2.3,
            "invoice_id": 2.2,
            "vehicle_id": 2.4,
            "license_plate": 2.3,
            "vin": 2.4,
            "sku": 2.3,
            "barcode": 2.2,
            "serial_number": 2.3,
            "asset_id": 2.3,
            "ticket_id": 2.2,
            "account_id": 2.2,
            "employee_id": 2.2,
            "national_id": 2.1,
            "phone": 1.6,
            "name": 0.9,
            "application_date": 0.3,
            "date": 0.2,
            "department": -0.2,
            "position": -0.1,
            "status": -0.9,
            "score": -0.8,
            "note": -0.9,
            "comment": -0.9,
            "salary": -0.4,
        }
        return weights.get(canonical, 0.0)

    @staticmethod
    def _can_use_single_key(identity_weight: float, stats: dict, row_count: int) -> bool:
        if identity_weight >= 0.8:
            return True
        return row_count >= 8 and stats["unique_avg"] >= 0.85 and stats["overlap"] >= 0.50

    @staticmethod
    def _is_volatile_column(canonical: str) -> bool:
        return canonical in {
            "status", "score", "note", "comment", "salary", "result", "source",
            "amount", "price", "quantity", "stock", "mileage", "date", "application_date",
        }

    def _unmapped_columns(self, df_a: pd.DataFrame, df_b: pd.DataFrame, mapping: list[dict]) -> dict:
        mapped_a = {item["a"] for item in mapping}
        mapped_b = {item["b"] for item in mapping}
        return {
            "a": [str(col) for col in df_a.columns if str(col) not in mapped_a],
            "b": [str(col) for col in df_b.columns if str(col) not in mapped_b],
        }

    @staticmethod
    def _comparison_summary(result: dict, mapping: list[dict], key_columns: list[str]) -> dict:
        return {
            "mapped_column_count": len(mapping),
            "key_columns": key_columns,
            "matched_rows": result.get("matched_keys", 0),
            "changed_rows": result.get("changed_row_count", 0),
            "only_in_a": result.get("only_in_a_count", result.get("rows_only_in_a_count", 0)),
            "only_in_b": result.get("only_in_b_count", result.get("rows_only_in_b_count", 0)),
        }

    @staticmethod
    def _structure_summary(df_a: pd.DataFrame, df_b: pd.DataFrame, mapping: list[dict]) -> dict:
        return {
            "rows": {"a": int(len(df_a)), "b": int(len(df_b)), "delta": int(len(df_b) - len(df_a))},
            "columns": {"a": int(len(df_a.columns)), "b": int(len(df_b.columns)), "delta": int(len(df_b.columns) - len(df_a.columns))},
            "same_column_order": [str(col) for col in df_a.columns] == [str(col) for col in df_b.columns],
            "mapped_column_count": len(mapping),
        }

    def _key_quality(self, df_a: pd.DataFrame, df_b: pd.DataFrame, key_columns: list[str]) -> dict:
        if not key_columns:
            return {"status": "fallback"}
        if len(key_columns) == 1:
            stats = self._key_stats(df_a, df_b, key_columns[0])
        else:
            tuple_stats = self._tuple_key_stats(df_a, df_b, key_columns)
            stats = {"unique_avg": tuple_stats["unique_avg"], "overlap": tuple_stats["overlap"], "non_null_avg": 1.0}
        confidence = "high"
        if stats["unique_avg"] < 0.8 or stats["overlap"] < 0.35:
            confidence = "medium"
        if stats["unique_avg"] < 0.6 or stats["overlap"] < 0.15:
            confidence = "low"
        return {
            "status": "keyed",
            "confidence": confidence,
            "key_columns": key_columns,
            "unique_avg": round(float(stats["unique_avg"]), 3),
            "overlap": round(float(stats["overlap"]), 3),
            "non_null_avg": round(float(stats.get("non_null_avg", 1.0)), 3),
        }

    @staticmethod
    def _is_known_canonical(canonical: str) -> bool:
        return canonical in ExcelCompareService._column_aliases()

    @staticmethod
    def _canonical_column(column: str) -> str:
        norm = normalize_column_name(column)
        if norm == "id":
            return "record_id"
        for canonical, hints in ExcelCompareService._column_aliases().items():
            if any(ExcelCompareService._hint_matches(norm, hint) for hint in hints):
                return canonical
        return norm

    @staticmethod
    def _hint_matches(norm: str, hint: str) -> bool:
        hint_norm = normalize_column_name(hint)
        if not hint_norm:
            return False
        if " " in hint_norm:
            return hint_norm in norm
        tokens = set(norm.split())
        if hint_norm in tokens or hint_norm == norm:
            return True
        return len(hint_norm) > 4 and hint_norm in norm

    @staticmethod
    def _column_aliases() -> dict[str, tuple[str, ...]]:
        return {
            "record_id": ("record id", "record no", "row id", "kayit id", "kayit no", "kayıt id", "kayıt no"),
            "unique_id": ("unique id", "uniq id", "uuid", "guid", "tekil id"),
            "email": ("email", "e posta", "e-mail", "mail"),
            "phone": ("telefon", "phone", "gsm", "cep", "mobile", "cell", "contact number"),
            "national_id": ("tc kimlik", "kimlik no", "national id", "identity number"),
            "name": ("ad soyad", "isim soyisim", "isim", "name", "full name", "candidate name", "applicant name"),
            "candidate_id": (
                "aday id", "candidate id", "candidate no", "aday no", "basvuru id", "basvuru no",
                "application id", "applicant id", "reference id", "ref no",
            ),
            "customer_id": ("customer id", "customer no", "client id", "client no", "musteri id", "musteri no", "müşteri id", "müşteri no"),
            "product_id": ("product id", "product no", "urun id", "urun no", "ürün id", "ürün no", "item id", "item no"),
            "order_id": ("order id", "order no", "siparis id", "siparis no", "sipariş id", "sipariş no"),
            "transaction_id": ("transaction id", "transaction no", "islem id", "islem no", "işlem id", "işlem no", "txn id"),
            "invoice_id": ("invoice id", "invoice no", "fatura id", "fatura no", "bill no"),
            "vehicle_id": ("vehicle id", "vehicle no", "arac id", "arac no", "araç id", "araç no"),
            "license_plate": ("plaka", "plate", "license plate", "plate no", "registration no"),
            "vin": ("vin", "sasi no", "şasi no", "chassis no", "chassis number"),
            "sku": (
                "sku", "stock code", "stok kodu", "urun kodu", "ürün kodu", "item code", "product code",
                "material code", "malzeme kodu", "part number", "part no", "parca no", "parça no",
            ),
            "barcode": ("barcode", "barkod", "ean", "gtin"),
            "serial_number": ("serial no", "serial number", "seri no", "seri numarasi", "seri numarası"),
            "asset_id": ("asset id", "asset no", "demirbas no", "demirbaş no", "varlik id", "varlık id"),
            "ticket_id": ("ticket id", "ticket no", "talep no", "case id", "case no"),
            "account_id": ("account id", "account no", "hesap no", "hesap id"),
            "employee_id": ("calisan kodu", "calisan no", "employee id", "employee no", "sicil", "personel no", "personnel no"),
            "status": (
                "aday durumu", "form durumu", "basvuru durumu", "application status", "candidate status",
                "status", "stage", "phase", "step", "asama", "durum", "son durum", "state", "condition",
            ),
            "department": (
                "departman", "direktorluk", "mudurluk", "birim", "bolum", "department", "directorate",
                "division", "business unit", "unit", "team", "ekip",
            ),
            "position": (
                "pozisyon", "basvurulan pozisyon", "role", "job", "job title", "title", "unvan",
                "gorev", "position", "applied role",
            ),
            "source": ("kaynak", "source", "kanal", "channel", "platform", "referral"),
            "application_date": ("basvuru tarihi", "application date", "apply date", "applied date"),
            "date": ("tarih", "date", "created at", "updated at", "start date", "end date", "baslangic tarihi", "bitiş tarihi", "bitis tarihi"),
            "city": ("sehir", "il", "lokasyon", "location", "city", "province"),
            "country": ("ulke", "ülke", "country"),
            "region": ("bolge", "bölge", "region", "area"),
            "address": ("adres", "address"),
            "education": ("egitim", "education", "degree", "mezuniyet"),
            "university": ("universite", "university", "school", "okul"),
            "experience": ("deneyim", "experience", "work experience", "years of experience", "tecrube", "kidem"),
            "skills": ("yetkinlik", "beceri", "skills", "technical skills", "competencies", "technology"),
            "score": ("skor", "puan", "score", "rating", "grade", "degerlendirme notu", "assessment score"),
            "result": ("sonuc", "result", "outcome", "decision", "karar"),
            "amount": ("tutar", "amount", "total amount", "toplam tutar", "bedel"),
            "price": ("fiyat", "price", "unit price", "birim fiyat", "cost", "maliyet"),
            "quantity": ("adet", "miktar", "quantity", "qty", "count"),
            "stock": ("stok", "stock", "inventory", "envanter"),
            "salary": ("maas", "ucret", "salary", "expected salary", "beklenen ucret"),
            "note": ("not", "notes", "aciklama", "description"),
            "comment": ("yorum", "comment", "feedback", "geribildirim", "review"),
            "category": ("kategori", "category", "class", "sinif", "sınıf", "segment", "type", "tip"),
            "brand": ("marka", "brand", "make"),
            "model": ("model", "vehicle model", "urun modeli", "ürün modeli"),
            "color": ("renk", "color", "colour"),
            "year": ("yil", "yıl", "year", "model year"),
            "mileage": ("km", "kilometre", "kilometer", "mileage", "odometer"),
            "warehouse": ("depo", "warehouse", "storage", "lokasyon depo"),
            "owner": ("sahip", "owner", "responsible", "sorumlu"),
            "language": ("dil", "language", "languages"),
            "certification": ("sertifika", "certification", "certificate"),
            "recruiter": ("recruiter", "ik sorumlusu", "hr owner", "owner"),
            "interviewer": ("gorusmeci", "interviewer", "interview owner"),
        }


excel_compare_service = ExcelCompareService()
