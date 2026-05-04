"""Excel export helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import settings
from app.utils.file_utils import ensure_parent, make_job_id, safe_filename


def export_dataframe(df: pd.DataFrame, name: str, job_id: str | None = None) -> str:
    job = job_id or make_job_id("export")
    output = settings.EXPORT_DIR / job / f"{safe_filename(name)}.xlsx"
    ensure_parent(output)
    df.to_excel(output, index=False, engine="openpyxl")
    return str(output.resolve())


def export_multiple_sheets(sheets: dict[str, pd.DataFrame], name: str, job_id: str | None = None) -> str:
    job = job_id or make_job_id("export")
    output = settings.EXPORT_DIR / job / f"{safe_filename(name)}.xlsx"
    ensure_parent(output)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=safe_filename(sheet_name)[:31])
    return str(output.resolve())
