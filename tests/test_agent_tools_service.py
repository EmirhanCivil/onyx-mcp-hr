import pandas as pd

from app.config import settings
from app.core.file_registry import file_registry
from app.services.cv_service import cv_service
from app.tools.agent_tools import register_agent_tools


def test_cv_answer_question_returns_detail_profile(tmp_path, monkeypatch):
    upload_dir = tmp_path / "cv"
    upload_dir.mkdir()
    (upload_dir / "candidate.txt").write_text(
        "\n".join([
            "Ada Lovelace",
            "Data Scientist | Istanbul | ada@example.com | 0532 111 22 33",
            "Özet Profil",
            "Python ve SQL deneyimi.",
            "Kişisel ve Başvuru Bilgileri",
            "Aday ID",
            "ADY-99999",
            "Direktörlük",
            "Veri",
            "Eğitim",
            "ODTÜ - Matematik",
            "Teknik Yetkinlikler",
            "Python, SQL",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "CV_UPLOAD_DIR", upload_dir)
    cv_service._meta.clear()
    cv_service._texts.clear()

    result = cv_service.answer_question("ADY-99999 egitim ve yetkinlik detaylari")

    assert result["mode"] == "detail"
    assert result["profiles"][0]["candidate_id"] == "ADY-99999"
    assert result["profiles"][0]["education"] == "ODTÜ - Matematik"


def test_register_agent_tools_smoke():
    class DummyMcp:
        def tool(self):
            return lambda fn: fn

        def prompt(self):
            return lambda fn: fn

    register_agent_tools(DummyMcp())


def test_cv_profile_normalizes_turkish_labels(tmp_path, monkeypatch):
    upload_dir = tmp_path / "cv"
    upload_dir.mkdir()
    (upload_dir / "candidate.txt").write_text(
        "Mehmet Test\nDeveloper | Ankara | mehmet@example.com | 0532 111 22 33\nDirektörlük\nYazılım\nEğitim\nİTÜ - Bilgisayar\nTeknik Yetkinlikler\nPython, Docker",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "CV_UPLOAD_DIR", upload_dir)
    cv_service._meta.clear()
    cv_service._texts.clear()
    cv_service.scan_cvs()

    detail = cv_service.get_cv_detail(query="Mehmet")

    assert detail["directorate"] == "Yazılım"
    assert detail["education"] == "İTÜ - Bilgisayar"


def test_cv_profile_extracts_english_cv_sections(tmp_path, monkeypatch):
    upload_dir = tmp_path / "cv"
    upload_dir.mkdir()
    (upload_dir / "english_candidate.txt").write_text(
        "\n".join([
            "Jane Smith",
            "Data Engineer | London | jane@example.com | 0532 111 22 33",
            "Professional Summary",
            "Data engineer with Python and Spark experience.",
            "Personal Information",
            "Candidate ID",
            "CAND-100",
            "Status",
            "Interview",
            "Department",
            "Data Platform",
            "Source",
            "LinkedIn",
            "Education",
            "University of Manchester - Computer Science (2019)",
            "Technical Skills",
            "Python, SQL, Spark, Airflow",
            "Work Experience",
            "- 2021-2026: Data Engineer - Built data pipelines.",
            "Projects",
            "- Lakehouse migration",
            "Certifications and Languages",
            "Certifications: AWS Data Analytics",
            "Languages: English - C1, Turkish - A2",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "CV_UPLOAD_DIR", upload_dir)
    cv_service._meta.clear()
    cv_service._texts.clear()
    cv_service.scan_cvs()

    detail = cv_service.get_cv_detail(query="CAND-100 education skills")

    assert detail["candidate_id"] == "CAND-100"
    assert detail["form_status"] == "Interview"
    assert detail["directorate"] == "Data Platform"
    assert detail["education"] == "University of Manchester - Computer Science (2019)"
    assert "Spark" in detail["skills"]
    assert detail["experience"] == ["2021-2026: Data Engineer - Built data pipelines."]
    assert detail["projects"] == ["Lakehouse migration"]
