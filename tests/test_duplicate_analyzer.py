import pandas as pd

from app.analyzers.duplicate_analyzer import deduplicate, find_duplicates


def test_find_duplicates_by_key_columns():
    df = pd.DataFrame({
        "student_id": [1, 1, 2, 3],
        "email": ["a@example.com", "a@example.com", "b@example.com", "c@example.com"],
        "status": ["sent", "sent", "pending", "sent"],
    })

    result = find_duplicates(df, ["student_id", "email"])

    assert result["duplicate_group_count"] == 1
    assert result["duplicate_row_count"] == 2
    assert result["unique_after_dedup"] == 3


def test_deduplicate_keeps_first_record():
    df = pd.DataFrame({"id": [1, 1, 2], "value": ["old", "new", "single"]})

    cleaned, summary = deduplicate(df, ["id"], keep="first")

    assert len(cleaned) == 2
    assert cleaned.iloc[0]["value"] == "old"
    assert summary["removed_rows"] == 1
