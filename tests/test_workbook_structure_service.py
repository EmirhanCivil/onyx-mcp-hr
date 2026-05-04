import pandas as pd

from app.core.file_registry import file_registry
from app.services.excel_service import excel_service
from app.services.workbook_structure_service import workbook_structure_service


def test_analyze_workbook_structure_detects_multiple_data_sheets(tmp_path):
    file_registry.clear()

    workbook = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame({"Note": ["This is a cover sheet"]}).to_excel(writer, sheet_name="Cover", index=False)
        pd.DataFrame({"ID": ["A1", "A2", "A3"], "Status": ["New", "Done", "New"], "Score": [1, 2, 3]}).to_excel(
            writer, sheet_name="Case 01", index=False
        )
        pd.DataFrame({"ID": ["B1", "B2"], "Comment": ["good process", "too much workload"]}).to_excel(
            writer, sheet_name="Anything", index=False
        )

    loaded = excel_service.load_file(str(workbook), sheet_name="auto")
    file_id = loaded["file"]["file_id"]

    result = workbook_structure_service.analyze(file_id=file_id, task_hint="yorum analizi")
    assert result["total_sheets"] == 3
    assert len(result["analyzable_sheets"]) >= 1
    assert any(item["classification"] == "data_sheet" for item in result["analyzable_sheets"])
