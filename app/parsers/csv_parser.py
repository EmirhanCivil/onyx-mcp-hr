"""CSV parser with basic encoding fallback."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.exceptions import FileProcessingError


ENCODINGS = ("utf-8", "utf-8-sig", "cp1254", "iso-8859-9", "latin-1")


def read_csv_file(file_path: str, delimiter: str | None = None) -> pd.DataFrame:
    path = Path(file_path)
    if not path.exists():
        raise FileProcessingError(f"Dosya bulunamadı: {file_path}", code="FILE_NOT_FOUND")

    errors: list[str] = []
    for encoding in ENCODINGS:
        try:
            return pd.read_csv(path, sep=delimiter, engine="python", encoding=encoding)
        except UnicodeDecodeError as exc:
            errors.append(str(exc))
            continue
        except Exception as exc:
            raise FileProcessingError(f"CSV okunamadı: {exc}") from exc
    raise FileProcessingError(f"CSV encoding çözülemedi: {' | '.join(errors[:2])}")
