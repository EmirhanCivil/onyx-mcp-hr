"""Validation helpers shared by service methods."""

from __future__ import annotations

import pandas as pd

from app.core.exceptions import ColumnNotFoundError, InvalidInputError


def require_columns(df: pd.DataFrame, columns: list[str], label: str = "kolon") -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ColumnNotFoundError(f"Eksik {label}: {', '.join(missing)}")


def parse_columns(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def require_non_empty(value: str, field_name: str) -> None:
    if not value or not str(value).strip():
        raise InvalidInputError(f"{field_name} boş olamaz.")
