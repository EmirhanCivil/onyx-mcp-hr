"""JSON export helpers."""

from __future__ import annotations

import json

from app.config import settings
from app.utils.file_utils import ensure_parent, make_job_id, safe_filename


def export_json(data: dict, name: str, job_id: str | None = None) -> str:
    job = job_id or make_job_id("json")
    output = settings.EXPORT_DIR / job / f"{safe_filename(name)}.json"
    ensure_parent(output)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(output.resolve())
