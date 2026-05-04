import pandas as pd

from app.config import settings
from app.core.file_registry import file_registry
from app.services.cv_service import cv_service
from app.services.hr_service import hr_service


def _reset_state():
    file_registry.clear()
    cv_service._meta.clear()
    cv_service._texts.clear()


def test_candidate_shortlist_scores_required_and_preferred_terms(tmp_path, monkeypatch):
    _reset_state()
    upload_dir = tmp_path / "uploads" / "cv"
    upload_dir.mkdir(parents=True)
    (upload_dir / "candidate.txt").write_text("Python SQL pandas stakeholder reporting", encoding="utf-8")
    monkeypatch.setattr(settings, "CV_UPLOAD_DIR", upload_dir)

    result = hr_service.candidate_shortlist(
        role="Data Analyst",
        required_skills="Python, SQL",
        preferred_skills="pandas",
        limit=1,
    )

    assert result["shortlist"][0]["fit_score"] == 100
    assert result["shortlist"][0]["candidate"]
    assert result["shortlist"][0]["matched_required"] == ["Python", "SQL"]


def test_recruiting_pipeline_detects_stage_and_basic_quality(tmp_path, monkeypatch):
    _reset_state()
    root = tmp_path / "uploads"
    excel_dir = root / "excel"
    survey_dir = root / "survey"
    excel_dir.mkdir(parents=True)
    survey_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", root)
    monkeypatch.setattr(settings, "EXCEL_UPLOAD_DIR", excel_dir)
    monkeypatch.setattr(settings, "SURVEY_UPLOAD_DIR", survey_dir)

    df = pd.DataFrame({
        "Aday Durumu": ["Olumlu", "Olumsuz", "Bekliyor"],
        "Basvurulan Pozisyon": ["Analyst", "Analyst", "Engineer"],
        "Kaynak Kanali": ["LinkedIn", "Kariyer", "LinkedIn"],
        "Direktorluk": ["HR", "HR", "IT"],
        "Cinsiyet": ["Kadin", "Erkek", "Kadin"],
    })
    df.to_excel(excel_dir / "applicants.xlsx", index=False)

    result = hr_service.recruiting_pipeline()

    assert result["columns_used"]["stage_column"] == "Aday Durumu"
    assert result["row_count"] == 3
    assert "missing_rates_percent" in result["data_quality"]


def test_survey_action_plan_exports_action_files(tmp_path, monkeypatch):
    _reset_state()
    root = tmp_path / "uploads"
    excel_dir = root / "excel"
    survey_dir = root / "survey"
    report_dir = tmp_path / "reports"
    export_dir = tmp_path / "exports"
    excel_dir.mkdir(parents=True)
    survey_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", root)
    monkeypatch.setattr(settings, "EXCEL_UPLOAD_DIR", excel_dir)
    monkeypatch.setattr(settings, "SURVEY_UPLOAD_DIR", survey_dir)
    monkeypatch.setattr(settings, "REPORT_DIR", report_dir)
    monkeypatch.setattr(settings, "EXPORT_DIR", export_dir)

    df = pd.DataFrame({
        "Direktorluk": ["A", "A", "B", "B", "B"],
        "Genel Memnuniyet": [2, 3, 5, 4, 5],
        "Gelisim Yorumu": ["is yuku fazla", "surec yavas", "iyi", "iyi", "iyi"],
        "Aksiyon Onceligi": ["Yuksek", "Yuksek", "Dusuk", "Dusuk", "Dusuk"],
    })
    df.to_excel(survey_dir / "survey.xlsx", index=False)

    result = hr_service.survey_action_plan(export=True, min_group_size=1)

    assert result["action_plan"]["respondent_count"] == 5
    assert result["files"]
