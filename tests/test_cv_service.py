from app.config import settings
from app.services.cv_service import cv_service


def test_scan_cvs_loads_nested_supported_files(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads" / "cv"
    nested_dir = upload_dir / "engineering"
    nested_dir.mkdir(parents=True)
    (nested_dir / "candidate.txt").write_text("Python data analyst", encoding="utf-8")

    monkeypatch.setattr(settings, "CV_UPLOAD_DIR", upload_dir)
    cv_service._meta.clear()
    cv_service._texts.clear()

    result = cv_service.scan_cvs()

    assert result["loaded_count"] == 1
    assert result["failed_count"] == 0
    assert result["cvs"][0]["name"] == "candidate.txt"


def test_scan_cvs_handles_missing_folder(tmp_path, monkeypatch):
    missing_dir = tmp_path / "missing" / "cv"
    monkeypatch.setattr(settings, "CV_UPLOAD_DIR", missing_dir)
    cv_service._meta.clear()
    cv_service._texts.clear()

    result = cv_service.scan_cvs()

    assert result["loaded_count"] == 0
    assert result["failed_count"] == 1
    assert "CV klasoru bulunamadi" in result["failed"][0]["error"]


def test_get_cv_detail_extracts_structured_fields(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads" / "cv"
    upload_dir.mkdir(parents=True)
    (upload_dir / "candidate.txt").write_text(
        "\n".join([
            "Ada Lovelace",
            "Data Scientist | Istanbul | ada@example.com | 0532 111 22 33",
            "Ozet Profil",
            "Python ve SQL deneyimi.",
            "Kisisel ve Basvuru Bilgileri",
            "Aday ID",
            "ADY-99999",
            "Form Durumu",
            "Iletildi",
            "Egitim",
            "ODTU - Matematik (2020)",
            "Teknik Yetkinlikler",
            "Python, SQL, pandas",
            "Deneyim",
            "• 2022-2026: Data Scientist - Analitik projeler.",
            "Projeler",
            "• Churn modeli",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "CV_UPLOAD_DIR", upload_dir)
    cv_service._meta.clear()
    cv_service._texts.clear()
    cv_service.scan_cvs()

    detail = cv_service.get_cv_detail(query="ADY-99999")

    assert detail["name"] == "Ada Lovelace"
    assert detail["candidate_id"] == "ADY-99999"
    assert "Python" in detail["skills"]
    assert detail["text_quality"]["quality"] == "good"
