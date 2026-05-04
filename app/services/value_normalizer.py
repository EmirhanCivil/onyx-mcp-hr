"""Value normalization utilities for semantic spreadsheet comparison."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from app.utils.dataframe_utils import normalize_column_name


BINARY_TRUE = {
    "var",
    "evet",
    "yes",
    "true",
    "1",
    "mevcut",
    "aktif",
    "active",
    "gonderildi",
    "gönderildi",
    "iletildi",
    "sent",
    "delivered",
    "tamam",
    "ok",
}

BINARY_FALSE = {
    "yok",
    "hayir",
    "hayır",
    "no",
    "false",
    "0",
    "mevcut degil",
    "mevcut değil",
    "pasif",
    "inactive",
    "gonderilmedi",
    "gönderilmedi",
    "iletilmedi",
    "not sent",
    "undelivered",
    "bos",
    "boş",
    "null",
    "empty",
    "",
}


_CURRENCY = re.compile(r"[₺$€£]")
_PCT = re.compile(r"%")


def normalize_value(value: Any, value_type: str) -> Any:
    """Normalize a single cell value to a comparable representation.

    Returns:
      - binary: True/False/None
      - numeric: float/None
      - date: datetime.date/None
      - text: normalized string
      - id/key: normalized string
    """

    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return None

    vt = (value_type or "text").strip().lower()
    if vt in {"binary", "bool", "boolean"}:
        text = normalize_column_name(value)
        if text in {normalize_column_name(t) for t in BINARY_TRUE}:
            return True
        if text in {normalize_column_name(t) for t in BINARY_FALSE}:
            return False
        # Sometimes values are like "Evet (tamam)" -> contains match.
        if any(tok in text for tok in ("evet", "yes", "true", "aktif", "iletildi", "sent", "delivered")):
            return True
        if any(tok in text for tok in ("hayir", "no", "false", "pasif", "iletilmedi", "undelivered", "not sent")):
            return False
        return None

    if vt in {"numeric", "number", "float", "int", "currency", "percent"}:
        text = str(value).strip()
        if not text:
            return None
        negative = False
        if text.startswith("(") and text.endswith(")"):
            negative = True
            text = text[1:-1]
        text = _CURRENCY.sub("", text)
        is_percent = bool(_PCT.search(text))
        text = _PCT.sub("", text)
        text = text.replace(" ", "")
        # Handle thousand separators and decimal commas.
        # Cases: "1.200,50" -> 1200.50 ; "1,200.50" -> 1200.50
        if text.count(",") and text.count("."):
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        else:
            # Single separator -> treat comma as decimal.
            if text.count(",") == 1 and text.count(".") == 0:
                text = text.replace(",", ".")
            # Many dots -> thousand separators.
            if text.count(".") > 1 and text.count(",") == 0:
                text = text.replace(".", "")
        try:
            num = float(text)
        except ValueError:
            return None
        if negative:
            num = -num
        if is_percent:
            # keep as 0-100 scale (not 0-1) to match user expectations in reports
            return num
        return num

    if vt in {"date", "datetime"}:
        if isinstance(value, pd.Timestamp):
            return value.date()
        text = str(value).strip()
        if not text:
            return None
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
        if pd.isna(parsed):
            return None
        return parsed.date()

    # text / id / key
    text = str(value).strip()
    if not text:
        return ""
    return normalize_column_name(text)

