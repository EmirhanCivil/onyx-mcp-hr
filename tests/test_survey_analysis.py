import pandas as pd

from app.analyzers.comment_analyzer import analyze_comments
from app.analyzers.department_analyzer import group_scores
from app.analyzers.numeric_analyzer import summarize_numeric
from app.core.file_registry import file_registry
from app.services.survey_analysis_service import survey_analysis_service
from app.utils.column_detector import detect_columns


def test_numeric_summary_returns_mean():
    df = pd.DataFrame({"Memnuniyet": [1, 2, 3, None]})

    result = summarize_numeric(df, ["Memnuniyet"])

    assert result["Memnuniyet"]["mean"] == 2.0
    assert result["Memnuniyet"]["missing"] == 1


def test_group_scores_does_not_mask_small_groups():
    df = pd.DataFrame({
        "Departman": ["A", "A", "A", "A", "A", "B"],
        "Memnuniyet": [5, 4, 4, 5, 4, 1],
    })

    result = group_scores(df, "Departman", ["Memnuniyet"], min_group_size=5)

    groups = {item["group"] for item in result["groups"]}
    assert "A" in groups
    assert "B" in groups


def test_comment_theme_analysis_counts_themes():
    df = pd.DataFrame({"Yorum": ["yonetim iletisimi daha iyi olmali", "is yuku cok yogun ve stresli"]})

    result = analyze_comments(df, ["Yorum"])

    assert result["comment_count"] == 2
    assert sum(result["theme_counts"].values()) >= 2
    assert result["negative_themes"]
    assert result["risk_phrases"]


def test_detect_columns_returns_agent_ready_roles():
    df = pd.DataFrame({
        "Record ID": ["R1", "R2", "R3", "R4"],
        "Department": ["Sales", "Sales", "IT", "IT"],
        "Satisfaction Score": [4, 5, 2, 3],
        "Workload": [2, 3, 1, 2],
        "Feedback Comment": [
            "Manager communication is good",
            "Team support is good",
            "Workload is too high and stressful",
            "Career development is missing",
        ],
        "Created Date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
    })

    result = detect_columns(df)

    assert "Record ID" in result["key_columns"]
    assert "Department" in result["group_columns"]
    assert "Satisfaction Score" in result["likely_score_columns"]
    assert "Workload" in result["likely_score_columns"]
    assert "Feedback Comment" in result["comment_columns"]
    assert "Feedback Comment" not in result["key_columns"]
    assert "Created Date" in result["date_columns"]
    assert result["role_map"]["score"]


def test_survey_overview_builds_manager_ready_summary(tmp_path):
    file_registry.clear()
    df = pd.DataFrame({
        "Record ID": [f"R{i}" for i in range(1, 7)],
        "Department": ["Sales", "Sales", "Sales", "IT", "IT", "IT"],
        "Satisfaction Score": [4, 5, 4, 2, 3, 2],
        "Workload": [3, 3, 4, 1, 2, 1],
        "Feedback Comment": [
            "Manager communication is good",
            "Team support is good",
            "Communication is transparent",
            "Workload is too high and stressful",
            "Career development is missing",
            "Workload problem continues",
        ],
    })
    meta = file_registry.register(str(tmp_path / "survey.xlsx"), df, tags={"category": "survey"})

    overview = survey_analysis_service.overview(meta.file_id)
    manager_pack = survey_analysis_service.executive_summary(meta.file_id)

    assert overview["dataset_profile"]["row_count"] == 6
    assert overview["overall_metrics"]["response_count"] == 6
    assert overview["overall_metrics"]["overall_score"] is not None
    assert overview["executive_summary"]["summary_bullets"]
    assert "score_heatmap" in overview["recommended_outputs"]
    assert manager_pack["action_plan"]["actions"]
    assert manager_pack["risks"]["low_score_density_percent"]
