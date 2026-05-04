import os

import pandas as pd

from app.core.file_registry import file_registry
from app.services.excel_query_service import excel_query_service


def test_query_full_scan_exact_count_and_sample(tmp_path):
    file_registry.clear()
    df = pd.DataFrame(
        {
            "Universite": ["Sabanci Universitesi", "ODTU", "Sabancı Üniversitesi"],
            "Aday Durumu": ["IK Gorusmesi", "Teknik", "IK Görüşmesi"],
            "Ad Soyad": ["Ada", "Bora", "Cem"],
        }
    )
    meta = file_registry.register(str(tmp_path / "candidates.xlsx"), df, tags={"category": "excel"})

    result = excel_query_service.query_rows(
        file_id=meta.file_id,
        natural_query="sabanci ve ik gorusmesi kac tane",
        return_mode="count",
        sample_limit=10,
    )

    data = result["data"]
    assert data["scan_mode"] == "full"
    assert data["is_result_complete"] is True
    assert data["total_rows_scanned"] == 3
    # "sabanci" + "ik gorusmesi" should match across different columns in the same row.
    assert data["matched_count"] == 2
    assert data["returned_rows_count"] == 0

    result2 = excel_query_service.query_rows(
        file_id=meta.file_id,
        natural_query="sabanci ve ik gorusmesi",
        return_mode="sample",
        sample_limit=1,
    )
    data2 = result2["data"]
    assert data2["matched_count"] == 2
    assert data2["returned_rows_count"] == 1
    assert len(data2["sample_rows"]) == 1


def test_query_structured_column_resolution_and_export(tmp_path):
    file_registry.clear()
    df = pd.DataFrame(
        {
            "Üniversite": ["Sabancı Üniversitesi", "Boğaziçi"],
            "Durum": ["İK Görüşmesi", "Beklemede"],
            "Email": ["ada@example.com", ""],
        }
    )
    meta = file_registry.register(str(tmp_path / "hr.xlsx"), df, tags={"category": "excel"})

    structured = {
        "conditions": [
            {"field": "okul", "operator": "contains", "value": "Sabanci"},
            {"field": "status", "operator": "contains", "value": "ik gorusmesi"},
        ],
        "logic": "AND",
        "return_mode": "export",
        "sample_limit": 5,
    }

    result = excel_query_service.query_rows(
        file_id=meta.file_id,
        structured_query=structured,
        return_mode="export",
        sample_limit=5,
        export=True,
    )
    data = result["data"]
    assert data["matched_count"] == 1
    assert data["export_path"]
    assert os.path.exists(data["export_path"])
    assert any(item.get("type") == "file" for item in result.get("generated_outputs", []))


def test_query_natural_year_after_birthdate(tmp_path):
    file_registry.clear()
    df = pd.DataFrame(
        {
            "Doğum Tarihi": ["25/03/2002", "01/01/2003", "12/12/2004", "1999-05-01"],
            "Ad Soyad": ["A", "B", "C", "D"],
        }
    )
    meta = file_registry.register(str(tmp_path / "birth.xlsx"), df, tags={"category": "excel"})

    # "2002 sonrası" -> 2003+ (>= 2003-01-01)
    result = excel_query_service.query_rows(
        file_id=meta.file_id,
        natural_query="2002 sonrası doğumluları say",
        return_mode="count",
        sample_limit=10,
    )
    assert result["data"]["matched_count"] == 2
