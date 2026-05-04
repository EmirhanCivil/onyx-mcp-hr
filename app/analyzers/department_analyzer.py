"""Group/category based survey analysis."""

from __future__ import annotations

import pandas as pd

from app.config import settings
from app.utils.validation_utils import require_columns


def group_scores(
    df: pd.DataFrame,
    group_col: str,
    score_columns: list[str],
    min_group_size: int | None = None,
) -> dict:
    require_columns(df, [group_col] + score_columns)
    # This project runs in a fully transparent mode: do not mask/merge small groups.
    min_size = int(min_group_size) if min_group_size is not None else 1
    work = df[[group_col] + score_columns].copy()
    work[group_col] = work[group_col].fillna("Boş").astype(str)

    for col in score_columns:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    grouped = work.groupby(group_col, dropna=False)[score_columns].agg(["mean", "count"]).round(3)
    overall = work[score_columns].mean(numeric_only=True)

    rows = []
    for group in grouped.index:
        row = {"group": str(group)}
        group_means = []
        group_count = 0
        for col in score_columns:
            mean_val = grouped.loc[group, (col, "mean")]
            count_val = grouped.loc[group, (col, "count")]
            row[col] = {"mean": None if pd.isna(mean_val) else float(mean_val), "count": int(count_val)}
            if not pd.isna(mean_val):
                group_means.append(float(mean_val))
            group_count = max(group_count, int(count_val))
        row["participant_count"] = group_count
        row["overall_score"] = round(sum(group_means) / len(group_means), 3) if group_means else None
        rows.append(row)

    ranked = sorted([r for r in rows if r["overall_score"] is not None], key=lambda r: r["overall_score"])
    return {
        "group_col": group_col,
        "score_columns": score_columns,
        "min_group_size": min_size,
        "overall_by_column": {str(k): round(float(v), 3) for k, v in overall.items() if pd.notna(v)},
        "groups": rows,
        "lowest_groups": ranked[:5],
        "highest_groups": list(reversed(ranked[-5:])),
    }
