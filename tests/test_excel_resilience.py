import pandas as pd

from app.core.file_registry import file_registry
from app.parsers.excel_parser import list_excel_sheets, read_excel_file
from app.services.excel_compare_service import excel_compare_service
from app.services.excel_service import excel_service


def test_auto_sheet_selection_picks_populated_sheet(tmp_path):
    workbook = tmp_path / "multi_sheet.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame({"Not": []}).to_excel(writer, sheet_name="Intro", index=False)
        pd.DataFrame({"Aday ID": ["A1", "A2"], "Durum": ["Yeni", "Olumlu"]}).to_excel(writer, sheet_name="Data", index=False)

    sheets = list_excel_sheets(str(workbook))
    df = read_excel_file(str(workbook), sheet_name="auto")

    assert len(sheets) == 2
    assert list(df.columns) == ["Aday ID", "Durum"]
    assert len(df) == 2


def test_quality_audit_flags_duplicates_without_sensitive_fields(tmp_path):
    file_registry.clear()
    df = pd.DataFrame({
        "Email": ["a@example.com", "a@example.com", "b@example.com"],
        "Status": ["New", "New", "Done"],
        "Empty": [None, None, None],
    })
    meta = file_registry.register(str(tmp_path / "candidates.xlsx"), df, tags={"category": "candidate"})

    result = excel_service.audit_quality(meta.file_id)

    assert result["quality"]["duplicate_row_count"] == 2
    assert "Empty" in result["quality"]["empty_columns"]


def test_auto_compare_maps_equivalent_column_names(tmp_path):
    file_registry.clear()
    a = pd.DataFrame({
        "E-posta": ["a@example.com", "b@example.com"],
        "Aday Durumu": ["Bekliyor", "Olumlu"],
    })
    b = pd.DataFrame({
        "Email": ["a@example.com", "b@example.com"],
        "Status": ["Olumlu", "Olumlu"],
    })
    meta_a = file_registry.register(str(tmp_path / "old.xlsx"), a, tags={"category": "candidate"})
    meta_b = file_registry.register(str(tmp_path / "new.xlsx"), b, tags={"category": "candidate"})

    result = excel_compare_service.compare_auto(meta_a.file_id, meta_b.file_id, key_query="email")

    assert result["comparison_mode"] == "keyed"
    assert result["inferred_key_columns"] == ["E-posta"]
    assert result["changed_row_count"] == 1
