"""Excel parser for workbook files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.exceptions import FileProcessingError


def read_excel_file(file_path: str, sheet_name: str | int | None = 0) -> pd.DataFrame:
    path = Path(file_path)
    if not path.exists():
        raise FileProcessingError(f"Dosya bulunamadi: {file_path}", code="FILE_NOT_FOUND")
    try:
        if sheet_name is None or str(sheet_name).strip().lower() in {"", "auto", "best"}:
            sheet_name = pick_best_sheet(str(path))
        return pd.read_excel(path, sheet_name=sheet_name)
    except Exception as exc:
        raise FileProcessingError(f"Excel okunamadi: {exc}") from exc


def resolve_sheet_name(file_path: str, sheet_name: str | int | None = 0) -> str | int:
    """Resolve 'auto' / None to a concrete sheet name."""

    path = Path(file_path)
    if sheet_name is None or str(sheet_name).strip().lower() in {"", "auto", "best"}:
        return pick_best_sheet(str(path))
    return sheet_name


def list_excel_sheets(file_path: str) -> list[dict]:
    """Return lightweight sheet inventory without exposing workbook data."""

    path = Path(file_path)
    if not path.exists():
        raise FileProcessingError(f"Dosya bulunamadi: {file_path}", code="FILE_NOT_FOUND")
    try:
        workbook = pd.ExcelFile(path)
        sheets = []
        for sheet in workbook.sheet_names:
            preview = pd.read_excel(path, sheet_name=sheet, nrows=25)
            preview = preview.dropna(how="all").dropna(axis=1, how="all")
            sheets.append({
                "sheet_name": sheet,
                "preview_rows": int(len(preview)),
                "preview_columns": int(len(preview.columns)),
                "non_empty_preview_cells": int(preview.notna().sum().sum()),
                "column_preview": [str(col).strip() for col in preview.columns[:30]],
            })
        return sheets
    except Exception as exc:
        raise FileProcessingError(f"Excel sheet envanteri okunamadi: {exc}") from exc


def pick_best_sheet(file_path: str) -> str | int:
    """Pick the sheet that looks most like a real table."""

    sheets = list_excel_sheets(file_path)
    if not sheets:
        return 0
    ranked = sorted(
        sheets,
        key=lambda item: (item["non_empty_preview_cells"], item["preview_rows"], item["preview_columns"]),
        reverse=True,
    )
    return ranked[0]["sheet_name"]
