"""Markdown report export."""

from __future__ import annotations

from app.config import settings
from app.utils.file_utils import ensure_parent, make_job_id, safe_filename


def export_markdown(content: str, name: str, job_id: str | None = None) -> str:
    job = job_id or make_job_id("report")
    output = settings.REPORT_DIR / job / f"{safe_filename(name)}.md"
    ensure_parent(output)
    output.write_text(content, encoding="utf-8")
    return str(output.resolve())
