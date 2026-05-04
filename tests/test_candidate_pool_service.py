import pandas as pd

from app.core.file_registry import file_registry
from app.services.candidate_pool_service import candidate_pool_service
from app.services.excel_cv_match_service import excel_cv_match_service
from app.services.cv_service import cv_service
from app.config import settings


def test_candidate_pool_analyze_detects_distributions_and_duplicates(tmp_path):
    file_registry.clear()
    df = pd.DataFrame(
        {
            "Aday Durumu": ["IK Goruşmesi", "Beklemede", "IK Görüşmesi", "Beklemede"],
            "Üniversite": ["Sabancı", "ODTU", "Sabanci", ""],
            "Email": ["a@x.com", "b@x.com", "a@x.com", ""],
            "Telefon": ["5551112233", "5559998877", "5551112233", ""],
        }
    )
    meta = file_registry.register(str(tmp_path / "pool.xlsx"), df, tags={"category": "candidate"})

    result = candidate_pool_service.analyze(file_id=meta.file_id, limit=5, export=False)
    data = result["data"]

    assert data["row_count"] == 4
    assert data["resolved_columns"]["status"] in df.columns
    assert any(item["value"] == "IK Goruşmesi" or item["value"] == "IK Görüşmesi" for item in data["distributions"]["status"])
    assert data["duplicates"]["duplicate_row_count"] >= 1


def test_excel_cv_match_reports_unmatched_candidates(tmp_path):
    # Put test CVs into the real CV uploads dir so scan_cvs() can find them.
    test_email = "test_ada_match_123@example.com"
    test_phone = "+90 555 111 22 33"
    cv1 = settings.CV_UPLOAD_DIR / "TEST_Ada_Yilmaz_match.txt"
    cv2 = settings.CV_UPLOAD_DIR / "TEST_Bora_Demir_unrelated.txt"
    cv1.write_text(f"Email: {test_email} Phone: {test_phone}", encoding="utf-8")
    cv2.write_text("Email: unrelated_cv@example.com Phone: +90 555 999 88 77", encoding="utf-8")
    cv_service.scan_cvs()

    file_registry.clear()
    df = pd.DataFrame(
        {
            "Email": [test_email, "cem@example.com"],
            "Telefon": ["05551112233", "05550000000"],
            "Ad Soyad": ["Ada Yilmaz", "Cem Kaya"],
        }
    )
    meta = file_registry.register(str(tmp_path / "candidates.xlsx"), df, tags={"category": "candidate"})

    try:
        result = excel_cv_match_service.match(file_id=meta.file_id, limit=10, export=False)
        data = result["data"]
        assert data["match_summary"]["matched_count"] == 1
        assert data["match_summary"]["unmatched_candidate_count"] == 1
    finally:
        # Cleanup test CV files
        for path in (cv1, cv2):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        cv_service.scan_cvs()
