"""Excel/CSV loading and profiling service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import settings
from app.core.exceptions import InvalidInputError
from app.core.file_registry import RegisteredFile, file_registry
from app.parsers.csv_parser import read_csv_file
from app.parsers.excel_parser import list_excel_sheets, read_excel_file, resolve_sheet_name
from app.utils.column_detector import detect_columns
from app.utils.dataframe_utils import dataframe_profile, normalize_column_name, safe_preview


class ExcelService:
    """Loads spreadsheets into the in-memory registry and returns compact metadata."""

    def load_file(
        self,
        file_path: str,
        sheet_name: str | int | None = 0,
        delimiter: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> dict:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext not in settings.SUPPORTED_SPREADSHEET_EXTENSIONS:
            raise InvalidInputError(f"Desteklenmeyen dosya formatı: {ext}")

        if ext == ".csv":
            df = read_csv_file(str(path), delimiter)
            resolved_sheet: str | int | None = None
        else:
            resolved_sheet = resolve_sheet_name(str(path), sheet_name)
            df = read_excel_file(str(path), resolved_sheet)

        df = self._normalize_headers(df)
        detected = detect_columns(df)
        merged_tags = self._classify_file(path, df, detected)
        if tags:
            merged_tags.update(tags)
        variant = None
        if resolved_sheet is not None:
            sheet_text = str(resolved_sheet)
            if sheet_text and sheet_text.strip().lower() not in {"0", "auto", "best"}:
                variant = f"sheet:{sheet_text}"
                merged_tags.setdefault("sheet_name", sheet_text)
        meta = file_registry.register(str(path), df, merged_tags, variant=variant)
        return self._response_for(meta, df)

    def scan_uploads(self) -> dict:
        """Load supported spreadsheets from structured upload folders into registry."""

        loaded = []
        failed = []
        scan_roots = (
            (settings.SURVEY_UPLOAD_DIR, {"category": "survey", "source": "survey_uploads"}),
            (settings.EXCEL_UPLOAD_DIR, {"source": "excel_uploads"}),
            (settings.UPLOAD_DIR, {"source": "uploads_scan"}),
        )
        seen: set[Path] = set()
        valid_paths: set[str] = set()
        managed_roots = [str(root) for root, _ in scan_roots]
        for root, tags in scan_roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                if not path.is_file() or path.suffix.lower() not in settings.SUPPORTED_SPREADSHEET_EXTENSIONS:
                    continue
                if path.parent == settings.UPLOAD_DIR and path.name.lower() in {"cv", "excel", "survey"}:
                    continue
                valid_paths.add(str(resolved))
                try:
                    loaded.append(self.load_file(str(path), sheet_name="auto", tags=tags)["file"])
                except Exception as exc:
                    failed.append({"path": str(path), "error": str(exc)})
        pruned_count = file_registry.prune_missing(valid_paths, managed_roots)
        return {
            "upload_dir": str(settings.UPLOAD_DIR),
            "structured_dirs": {
                "cv": str(settings.CV_UPLOAD_DIR),
                "excel": str(settings.EXCEL_UPLOAD_DIR),
                "survey": str(settings.SURVEY_UPLOAD_DIR),
            },
            "loaded_count": len(loaded),
            "failed_count": len(failed),
            "pruned_count": pruned_count,
            "files": loaded,
            "failed": failed,
            "categories": self.group_loaded_files(),
        }

    def profile(self, file_id: str, preview_rows: int = 10) -> dict:
        df = file_registry.get_frame(file_id)
        meta = file_registry.get_meta(file_id)
        data = self._response_for(meta, df)
        data["preview"] = safe_preview(df, preview_rows)
        return data

    def inspect_workbook(self, file_path: str) -> dict:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext not in {".xlsx", ".xls", ".xlsm", ".xlsb", ".ods"}:
            raise InvalidInputError("Workbook sheet envanteri sadece Excel dosyalari icin kullanilir.")
        sheets = list_excel_sheets(str(path))
        best = max(sheets, key=lambda item: item["non_empty_preview_cells"]) if sheets else None
        return {
            "path": str(path.resolve()),
            "sheet_count": len(sheets),
            "recommended_sheet": best["sheet_name"] if best else None,
            "sheets": sheets,
        }

    def audit_quality(self, file_id: str) -> dict:
        df = file_registry.get_frame(file_id)
        meta = file_registry.get_meta(file_id)
        detected = detect_columns(df)
        profile = dataframe_profile(df)
        empty_columns = [str(col) for col in df.columns if df[col].isna().all()]
        constant_columns = [
            str(col) for col in df.columns
            if df[col].nunique(dropna=False) <= 1 and not df[col].isna().all()
        ]
        mostly_missing = [
            str(col) for col, rate in profile["missing_rates_percent"].items()
            if rate >= 50
        ]
        duplicate_keys = self._suggest_key_columns(df, detected)
        duplicate_count = int(df.duplicated(subset=duplicate_keys, keep=False).sum()) if duplicate_keys else int(df.duplicated(keep=False).sum())
        warnings = []
        if empty_columns:
            warnings.append("Tamamen bos kolonlar var.")
        if mostly_missing:
            warnings.append("Yuzde 50 uzeri eksik veri iceren kolonlar var.")
        if duplicate_count:
            warnings.append("Muhtemel duplicate kayitlar var.")

        return {
            "file": meta.__dict__,
            "inferred_type": meta.tags.get("category", "other"),
            "profile": profile,
            "quality": {
                "empty_columns": empty_columns,
                "constant_columns": constant_columns,
                "mostly_missing_columns": mostly_missing,
                "duplicate_key_columns": duplicate_keys,
                "duplicate_row_count": duplicate_count,
            },
            "suggested_tools": self._suggest_tools(meta.tags.get("category", "other"), detected),
            "warnings": warnings,
        }

    def list_loaded_files(self) -> list[dict]:
        return [meta.__dict__ for meta in file_registry.list_files()]

    def group_loaded_files(self) -> dict:
        groups = {"survey": [], "candidate": [], "excel": [], "csv": [], "cv": [], "other": []}
        for meta in file_registry.list_files():
            category = meta.tags.get("category", "other")
            groups.setdefault(category, []).append(meta.__dict__)
        return groups

    def find_files(self, query: str = "", category: str = "") -> dict:
        query_norm = normalize_column_name(query)
        category_norm = category.strip().lower()
        matches = []
        scored = []
        for meta in file_registry.list_files():
            haystack = normalize_column_name(" ".join([meta.name, meta.path, " ".join(meta.columns), " ".join(meta.tags.values())]))
            meta_category = meta.tags.get("category", "other")
            if category_norm and not self._category_matches(meta_category, category_norm):
                continue
            score = self._match_score(query_norm, haystack)
            if query_norm and score == 0:
                continue
            scored.append((score, meta.__dict__))
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True):
            matches.append(item)
        return {"query": query, "category": category, "matches": matches, "match_count": len(matches)}

    def select_file(self, query: str = "", category: str = "") -> dict | None:
        result = self.find_files(query, category)
        if result["matches"]:
            return result["matches"][0]
        if category:
            fallback = self.find_files("", category)
            return fallback["matches"][0] if fallback["matches"] else None
        files = self.list_loaded_files()
        return files[0] if files else None

    def clear_file(self, file_id: str | None = None) -> dict:
        count = file_registry.clear(file_id)
        return {"cleared_count": count}

    @staticmethod
    def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        result.columns = [str(col).strip() for col in result.columns]
        return result

    @staticmethod
    def _response_for(meta: RegisteredFile, df: pd.DataFrame) -> dict:
        profile = dataframe_profile(df)
        return {
            "file": meta.__dict__,
            "profile": profile,
            "detected_columns": detect_columns(df),
            "guidance": {
                "use_file_id_for_next_tools": meta.file_id,
                "raw_rows_are_not_returned": True,
            },
        }

    @staticmethod
    def _classify_file(path: Path, df: pd.DataFrame, detected: dict) -> dict[str, str]:
        ext = path.suffix.lower()
        name = path.name.lower()
        likely_score_cols = detected.get("likely_score_columns", [])
        group_cols = detected.get("group_columns", [])
        comment_cols = detected.get("comment_columns", [])
        columns_text = normalize_column_name(" ".join(str(col) for col in df.columns))

        if ext == ".csv":
            category = "csv"
        elif likely_score_cols and (group_cols or comment_cols or "anket" in name or "survey" in name):
            category = "survey"
        elif any(token in columns_text or token in name for token in ("aday", "candidate", "basvuru", "applicant", "pozisyon", "cv", "resume")):
            category = "candidate"
        else:
            category = "excel"

        if "cv" in name or "resume" in name:
            category = "cv"

        return {
            "category": category,
            "source": "uploads_scan",
            "is_survey": str(category == "survey").lower(),
            "inferred_type": category,
            "row_count": str(len(df)),
        }

    @staticmethod
    def _suggest_key_columns(df: pd.DataFrame, detected: dict) -> list[str]:
        candidates = detected.get("key_columns", [])[:]
        for col in df.columns:
            norm = normalize_column_name(col)
            if any(token in norm for token in ("id", "kod", "no", "email", "mail")):
                candidates.append(str(col))
        unique = []
        for col in dict.fromkeys(candidates):
            if col in df.columns and df[col].notna().mean() >= 0.8 and df[col].nunique(dropna=True) / max(len(df), 1) >= 0.8:
                unique.append(col)
        return unique[:3]

    @staticmethod
    def _suggest_tools(category: str, detected: dict) -> list[str]:
        suggestions = ["profile_spreadsheet", "audit_spreadsheet_quality"]
        if category in {"candidate", "excel"}:
            suggestions.extend(["analyze_recruiting_pipeline", "auto_filter_excel_rows", "auto_compare_spreadsheets"])
        if category == "survey" or detected.get("likely_score_columns"):
            suggestions.extend(["auto_analyze_survey", "create_survey_action_plan"])
        if detected.get("key_columns"):
            suggestions.append("find_duplicate_rows")
        return list(dict.fromkeys(suggestions))

    @staticmethod
    def _match_score(query: str, haystack: str) -> int:
        if not query:
            return 1
        score = 0
        if query in haystack:
            score += len(query) + 20
        for token in query.split():
            if token and token in haystack:
                score += len(token)
        return score

    @staticmethod
    def _category_matches(meta_category: str, requested: str) -> bool:
        if meta_category == requested:
            return True
        if requested == "spreadsheet":
            return meta_category in {"excel", "candidate", "csv", "survey", "other"}
        if requested == "excel":
            return meta_category in {"excel", "candidate", "csv"}
        if requested in {"hr", "candidate", "applicant"}:
            return meta_category == "candidate"
        return False


excel_service = ExcelService()
