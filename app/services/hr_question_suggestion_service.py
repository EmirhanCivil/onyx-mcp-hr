"""Suggest useful questions based on loaded files and detected column roles."""

from __future__ import annotations

from app.services.cv_service import cv_service
from app.services.excel_service import excel_service
from app.utils.dataframe_utils import normalize_column_name


class HRQuestionSuggestionService:
    def suggest(self) -> dict:
        excel_service.scan_uploads()
        cv_service.scan_cvs()
        grouped = excel_service.group_loaded_files()
        suggestions = {
            "candidate_excel": [
                "Aday havuzunu ozetle (toplam aday, surec durum dagilimi, eksik veri, duplicate).",
                "Sabanci mezunu ve IK gorusmesinde olan kac aday var?",
                "Form bekleyen adaylari export et.",
                "Pozisyon bazli funnel analizi yap (top 10 pozisyon).",
                "Okul/sehir/pozisyon bazinda teknik gorusmeye gecis oranlarini karsilastir.",
                "Iki donem excel arasinda surec gecislerini analiz et (yeni/dusen/ilerleyen).",
                "Exceldeki adaylari CV dosyalariyla eslestir; CVsi olmayanlari export et.",
            ],
            "cv_library": [
                "Python ve SQL bilen adaylari bul ve ilk 10 eslesmeyi ozetle.",
                "Data Analyst rolu icin shortlist olustur (must-have: Python, SQL; nice-to-have: Power BI).",
                "CV kutuphanesini ozetle: en sik yetkinlikler, pozisyonlar ve dil/sertifika sinyalleri.",
            ],
            "survey": [
                "Anketi yonetici ozetiyle analiz et (guclu alanlar, riskli alanlar, en riskli gruplar).",
                "Departman risk raporu olustur ve en riskli 5 grubu ver.",
                "Yorumlardan tema/sentiment analizini ozetle ve aksiyon onceligi oner.",
                "Dusuk skor boyutlari icin kok neden analizi yap (tema + grup birlikte).",
            ],
        }

        return {
            "available_files": {k: len(v) for k, v in grouped.items()},
            "suggested_questions": suggestions,
        }


hr_question_suggestion_service = HRQuestionSuggestionService()

