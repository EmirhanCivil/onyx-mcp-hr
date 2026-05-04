"""HR column normalization utilities.

Provides a canonical, language-agnostic mapping for common HR fields, without requiring fixed schemas.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.utils.dataframe_utils import normalize_column_name


CANONICAL_FIELDS: dict[str, list[str]] = {
    "candidate_id": ["candidate id", "aday id", "applicant id", "record id", "id", "sicil", "numara", "number"],
    "full_name": ["ad soyad", "isim soyisim", "candidate name", "full name", "name surname", "name", "isim"],
    "email": ["email", "e-mail", "eposta", "e posta", "mail"],
    "phone": ["telefon", "phone", "gsm", "mobile", "cep"],
    "university": ["universite", "university", "school", "okul"],
    "major": ["bolum", "bölüm", "major", "program", "field of study", "department"],
    "city": ["sehir", "şehir", "city", "location", "lokasyon", "province"],
    "department": ["departman", "department", "direktorluk", "directorate", "birim", "unit", "team", "ekip"],
    "position": ["pozisyon", "position", "job", "role", "title", "unvan", "başvurulan pozisyon", "basvurulan pozisyon"],
    "status": ["aday durumu", "basvuru durumu", "form durumu", "status", "stage", "phase", "asama", "durum", "step"],
    "birth_date": ["dogum tarihi", "doğum tarihi", "birth date", "dob"],
    "military": ["askerlik", "military"],
    "comment": ["yorum", "comment", "feedback", "gorus", "görüş", "oner", "suggestion", "aciklama", "açıklama", "note", "not"],
    "score": ["skor", "score", "puan", "rating", "degerlendirme", "değerlendirme"],
    "source": ["kaynak", "source", "kanal", "channel", "platform"],
    "application_date": ["basvuru tarihi", "başvuru tarihi", "application date", "created at", "created", "date"],
}


@dataclass(frozen=True)
class FieldMatch:
    canonical: str
    resolved: str
    confidence: float
    strategy: str


class HRColumnNormalizationService:
    def normalize(self, df: pd.DataFrame, include_all_candidates: bool = False) -> dict:
        matches: dict[str, FieldMatch] = {}
        for canonical, hints in CANONICAL_FIELDS.items():
            match = self._resolve(df, canonical, hints)
            matches[canonical] = match

        mapping = {k: v.resolved for k, v in matches.items() if v.resolved}
        warnings = []
        low_conf = [m for m in matches.values() if m.resolved and m.confidence < 0.62]
        if low_conf:
            warnings.append("Bazi kolon eslestirmeleri belirsiz; kritik alanlar icin kolon adini netlestirebilirsiniz.")

        result = {
            "canonical_mapping": mapping,
            "match_details": {k: v.__dict__ for k, v in matches.items() if include_all_candidates or v.resolved},
            "warnings": warnings,
        }
        return result

    @staticmethod
    def normalize_status(value: object) -> dict:
        """Normalize HR stage/status into coarse buckets for dashboards and funnels."""
        text = normalize_column_name("" if value is None else value)
        if not text:
            return {"raw": value, "normalized": "unknown", "bucket": "unknown"}

        # Coarse buckets.
        if any(t in text for t in ("olumlu", "hired", "ise al", "kabul", "teklif", "offer", "accepted")):
            return {"raw": value, "normalized": "positive", "bucket": "positive"}
        if any(t in text for t in ("olumsuz", "reject", "rejected", "red", "elendi", "iptal", "declined")):
            return {"raw": value, "normalized": "negative", "bucket": "negative"}
        if any(t in text for t in ("ik gorus", "hr interview", "hr", "insan kaynaklari gorus")):
            return {"raw": value, "normalized": "hr_interview", "bucket": "in_process"}
        if any(t in text for t in ("teknik gorus", "technical interview", "case", "assignment", "challenge")):
            return {"raw": value, "normalized": "technical_interview", "bucket": "in_process"}
        if any(t in text for t in ("form", "belge", "dokuman", "doküman", "eksik", "missing")):
            return {"raw": value, "normalized": "form_waiting", "bucket": "waiting"}
        if any(t in text for t in ("bekle", "pending", "waiting", "hold")):
            return {"raw": value, "normalized": "waiting", "bucket": "waiting"}
        if any(t in text for t in ("new", "yeni", "basvuru", "başvuru", "applied", "screening", "tarama")):
            return {"raw": value, "normalized": "new", "bucket": "in_process"}
        return {"raw": value, "normalized": "other", "bucket": "in_process"}

    @staticmethod
    def _resolve(df: pd.DataFrame, canonical: str, hints: list[str]) -> FieldMatch:
        best = ""
        best_score = -1.0
        best_strategy = "fuzzy"
        hint_norms = [normalize_column_name(h) for h in hints]
        for col in df.columns:
            name = str(col)
            norm = normalize_column_name(name)
            if not norm:
                continue
            score = 0.0
            strategy = "fuzzy"
            for hint in hint_norms:
                if not hint:
                    continue
                if hint == norm:
                    score = max(score, 1.0)
                    strategy = "exact"
                elif hint in norm:
                    score = max(score, 0.92)
                    strategy = "substring"
                else:
                    # Token overlap score
                    ht = set(hint.split())
                    nt = set(norm.split())
                    if ht and nt:
                        overlap = len(ht & nt) / len(ht | nt)
                        score = max(score, overlap * 0.85)
            if score > best_score:
                best = name
                best_score = float(score)
                best_strategy = strategy
        if best_score <= 0:
            return FieldMatch(canonical, "", 0.0, "none")
        return FieldMatch(canonical, best, round(best_score, 3), best_strategy)


hr_column_normalization_service = HRColumnNormalizationService()

