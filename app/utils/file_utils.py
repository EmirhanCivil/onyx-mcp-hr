"""File and job path utilities."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
import unicodedata


def make_job_id(prefix: str = "job") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def safe_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).strip())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    ascii_text = ascii_text.replace("ı", "i").replace("İ", "I")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", ascii_text.lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return (cleaned[:90].strip("._") or "output")


def ensure_parent(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target
