from pathlib import Path

import pandas as pd

from app.config import settings
from app.core.file_registry import file_registry
from app.core.response_schema import ok_response
from app.services.chart_service import chart_service
from app.services.report_service import report_service
from app.services.survey_analysis_service import survey_analysis_service


def test_auto_survey_charts_and_report_generate_displayable_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CHART_DIR", tmp_path / "charts")
    monkeypatch.setattr(settings, "REPORT_DIR", tmp_path / "reports")
    file_registry.clear()
    df = pd.DataFrame({
        "Record ID": [f"R{i}" for i in range(1, 9)],
        "Department": ["Sales", "Sales", "Sales", "IT", "IT", "IT", "Ops", "Ops"],
        "Satisfaction Score": [4, 5, 4, 2, 3, 2, 4, 3],
        "Workload": [3, 3, 4, 1, 2, 1, 3, 3],
        "Feedback Comment": [
            "Manager communication is good",
            "Team support is good",
            "Communication is transparent",
            "Workload is too high and stressful",
            "Career development is missing",
            "Workload problem continues",
            "Process is clear",
            "Tools need improvement",
        ],
    })
    meta = file_registry.register(str(tmp_path / "survey.xlsx"), df, tags={"category": "survey"})

    visuals = chart_service.auto_survey_charts(meta.file_id)
    overview = survey_analysis_service.overview(meta.file_id)
    recommended = overview["recommended_group_analysis"]
    group = survey_analysis_service.by_group(meta.file_id, recommended["group_col"], ",".join(recommended["score_columns"]))
    comments = survey_analysis_service.comments(meta.file_id, ",".join(overview["recommended_comment_columns"]))
    report = report_service.create_survey_report(overview, group, comments, ["html"], visuals["charts"])
    response = ok_response(
        "test",
        "ok",
        {"visuals": visuals},
        files=report["files"] + [item["path"] for item in visuals["charts"]],
        charts=[item["path"] for item in visuals["charts"]],
        generated_outputs=report["generated_outputs"],
    )

    assert visuals["chart_count"] >= 2
    for output in visuals["charts"]:
        path = Path(output["path"])
        assert output["display"] is True
        assert output["mime_type"] == "image/png"
        assert path.exists()
        assert path.stat().st_size > 0
        assert " " not in path.name
    html_outputs = [item for item in report["generated_outputs"] if item["format"] == "html"]
    assert html_outputs
    html_path = Path(html_outputs[0]["path"])
    assert html_path.exists()
    assert "Yönetici" in html_path.read_text(encoding="utf-8")
    assert all(isinstance(item, dict) and "path" in item for item in response["generated_outputs"])
