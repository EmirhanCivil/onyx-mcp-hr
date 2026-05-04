"""Lightweight rule-based comment theme analysis for survey free text."""

from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from app.utils.validation_utils import require_columns


THEMES: dict[str, list[str]] = {
    "Yönetim ve liderlik": ["yönetim", "yonetim", "lider", "müdür", "mudur", "manager", "karar"],
    "İletişim": ["iletişim", "iletisim", "bilgilendirme", "duyuru", "şeffaf", "seffaf", "communication"],
    "İş yükü": ["iş yükü", "is yuku", "yoğun", "yogun", "fazla mesai", "mesai", "stres", "workload"],
    "Kariyer ve gelişim": ["kariyer", "terfi", "gelişim", "gelisim", "eğitim", "egitim", "öğrenme", "career"],
    "Ücret ve yan haklar": ["maaş", "maas", "ücret", "ucret", "prim", "yan hak", "benefit"],
    "Takdir ve motivasyon": ["takdir", "motivasyon", "ödül", "odul", "değer", "deger"],
    "Çalışma ortamı": ["ortam", "ekip", "ofis", "uzaktan", "hibrit", "araç", "arac", "team"],
    "Süreç ve araçlar": ["süreç", "surec", "sistem", "tool", "araç", "arac", "onay", "form", "process"],
}

POSITIVE = {"iyi", "memnun", "başarılı", "basarili", "güzel", "guzel", "olumlu", "destek", "mutlu", "good"}
NEGATIVE = {"kötü", "kotu", "yetersiz", "sorun", "problem", "şikayet", "sikayet", "zor", "eksik", "stres", "stressful", "missing"}
RISK_PHRASES = ("yetersiz", "sorun", "problem", "sikayet", "şikayet", "eksik", "stres", "stressful", "fazla mesai", "is yuku", "iş yükü", "workload")


def analyze_comments(df: pd.DataFrame, comment_columns: list[str], limit_examples: int = 5) -> dict:
    require_columns(df, comment_columns)
    comments = []
    for col in comment_columns:
        for value in df[col].dropna().astype(str):
            text = value.strip()
            if len(text) >= 3:
                comments.append(text)

    theme_counts: Counter[str] = Counter()
    sentiment_counts: Counter[str] = Counter()
    positive_theme_counts: Counter[str] = Counter()
    negative_theme_counts: Counter[str] = Counter()
    risk_phrase_counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = {theme: [] for theme in THEMES}

    for comment in comments:
        normalized = _normalize(comment)
        matched_themes = _matched_themes(normalized)
        for theme in matched_themes:
            theme_counts[theme] += 1
            if theme in examples and len(examples[theme]) < limit_examples:
                examples[theme].append(_truncate(comment))

        sentiment = _sentiment(normalized)
        sentiment_counts[sentiment] += 1
        if sentiment == "positive":
            positive_theme_counts.update(matched_themes)
        elif sentiment == "negative":
            negative_theme_counts.update(matched_themes)
            for phrase in RISK_PHRASES:
                if phrase in normalized:
                    risk_phrase_counts[phrase] += 1

    return {
        "comment_count": len(comments),
        "theme_counts": dict(theme_counts.most_common()),
        "sentiment_counts": dict(sentiment_counts),
        "positive_themes": _counter_items(positive_theme_counts),
        "negative_themes": _counter_items(negative_theme_counts),
        "risk_phrases": _counter_items(risk_phrase_counts, key_name="phrase"),
        "examples_by_theme": {k: v for k, v in examples.items() if v},
    }


def _matched_themes(normalized: str) -> list[str]:
    matched = [theme for theme, keywords in THEMES.items() if any(keyword in normalized for keyword in keywords)]
    return matched or ["Diğer / sınıflandırılamayan"]


def _sentiment(normalized: str) -> str:
    pos = sum(1 for word in POSITIVE if word in normalized)
    neg = sum(1 for word in NEGATIVE if word in normalized)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _truncate(text: str, max_len: int = 180) -> str:
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _counter_items(counter: Counter[str], limit: int = 10, key_name: str = "theme") -> list[dict]:
    return [{key_name: key, "count": int(value)} for key, value in counter.most_common(limit)]
