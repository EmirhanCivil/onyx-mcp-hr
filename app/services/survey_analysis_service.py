"""Survey analysis service for HR use cases."""

from __future__ import annotations

import pandas as pd

from app.analyzers.comment_analyzer import analyze_comments
from app.analyzers.department_analyzer import group_scores
from app.analyzers.numeric_analyzer import summarize_numeric
from app.core.file_registry import file_registry
from app.utils.column_detector import detect_columns
from app.utils.validation_utils import parse_columns


class SurveyAnalysisService:
    """Produces compact survey insights without exposing raw rows to the LLM."""

    def overview(self, file_id: str) -> dict:
        df = file_registry.get_frame(file_id)
        detected = detect_columns(df)
        score_cols = detected["likely_score_columns"] or detected["numeric_columns"]
        group_cols = detected["group_columns"]
        comment_cols = detected["comment_columns"]

        data = {
            "dataset_profile": _dataset_profile(df, detected),
            "detected_columns": detected,
            "numeric_summary": summarize_numeric(df, score_cols[:20]) if score_cols else {},
            "overall_metrics": _overall_metrics(df, score_cols[:20], group_cols),
        }
        if score_cols:
            data["interpretation"] = self._interpret_scores(data["numeric_summary"])
            data["executive_summary"] = _executive_summary(data["overall_metrics"], data["interpretation"], detected)
        if group_cols and score_cols:
            data["recommended_group_analysis"] = {
                "group_col": group_cols[0],
                "score_columns": score_cols[:10],
            }
        if comment_cols:
            data["recommended_comment_columns"] = comment_cols[:5]
        data["recommended_outputs"] = _recommended_outputs(score_cols, group_cols, comment_cols, detected["date_columns"])
        data["answer_guidance"] = (
            "Bu ciktiyi yonetici dostu ozetle: genel ozet, kritik bulgular, guclu alanlar, "
            "gelisime acik alanlar, tema sinyalleri ve aksiyon onerileri. Ham satir veya ham JSON basma."
        )
        return data

    def numeric(self, file_id: str, columns_csv: str) -> dict:
        df = file_registry.get_frame(file_id)
        return summarize_numeric(df, parse_columns(columns_csv))

    def by_group(self, file_id: str, group_col: str, score_columns_csv: str, min_group_size: int | None = None) -> dict:
        df = file_registry.get_frame(file_id)
        return group_scores(df, group_col, parse_columns(score_columns_csv), min_group_size)

    def comments(self, file_id: str, comment_columns_csv: str) -> dict:
        df = file_registry.get_frame(file_id)
        return analyze_comments(df, parse_columns(comment_columns_csv))

    def executive_summary(self, file_id: str, include_comments: bool = True) -> dict:
        overview = self.overview(file_id)
        df = file_registry.get_frame(file_id)
        detected = overview["detected_columns"]
        group_result = None
        comment_result = None
        recommended = overview.get("recommended_group_analysis")
        if recommended:
            group_result = self.by_group(file_id, recommended["group_col"], ",".join(recommended["score_columns"]))
        if include_comments and detected["comment_columns"]:
            comment_result = self.comments(file_id, ",".join(detected["comment_columns"][:5]))
        return _manager_pack(df, overview, group_result, comment_result)

    def compare_periods(
        self,
        file_id_a: str,
        file_id_b: str,
        group_col: str,
        score_columns_csv: str,
        min_group_size: int | None = None,
    ) -> dict:
        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)
        scores = parse_columns(score_columns_csv)
        a = group_scores(df_a, group_col, scores, min_group_size)
        b = group_scores(df_b, group_col, scores, min_group_size)

        a_scores = {row["group"]: row["overall_score"] for row in a["groups"]}
        b_scores = {row["group"]: row["overall_score"] for row in b["groups"]}
        changes = []
        for group in sorted(set(a_scores) | set(b_scores)):
            old = a_scores.get(group)
            new = b_scores.get(group)
            changes.append({
                "group": group,
                "period_a_score": old,
                "period_b_score": new,
                "change": round(new - old, 3) if old is not None and new is not None else None,
            })
        changes_sorted = sorted(
            [item for item in changes if item["change"] is not None],
            key=lambda item: item["change"],
        )
        return {
            "group_col": group_col,
            "score_columns": scores,
            "changes": changes,
            "largest_declines": changes_sorted[:5],
            "largest_improvements": list(reversed(changes_sorted[-5:])),
        }

    @staticmethod
    def _interpret_scores(numeric_summary: dict) -> dict:
        risks = []
        strengths = []
        for column, stats in numeric_summary.items():
            mean = stats.get("mean")
            if mean is None:
                continue
            item = {
                "column": column,
                "mean": mean,
                "signal": "neutral",
                "suggested_focus": "Takip icin segment ve yorum kirilimiyla birlikte yorumlayin.",
            }
            if mean <= 3.0:
                item["signal"] = "risk"
                item["suggested_focus"] = "Dusuk skor; departman/birim kirilimi ve yorum temalariyla aksiyon planina alin."
                risks.append(item)
            elif mean >= 4.0:
                item["signal"] = "strength"
                item["suggested_focus"] = "Guc alanini koruyun ve iyi pratikleri diger ekiplere yayin."
                strengths.append(item)
        return {
            "risk_columns": risks,
            "strength_columns": strengths,
            "guidance": "Skor yorumu tek basina karar degildir; grup buyuklugu, yorum temalari ve donem karsilastirmasi ile birlikte kullanin.",
        }


def _dataset_profile(df: pd.DataFrame, detected: dict) -> dict:
    missing = (df.isna().mean() * 100).round(2)
    missing_top = [
        {"column": str(column), "missing_percent": float(value)}
        for column, value in missing.sort_values(ascending=False).head(10).items()
        if float(value) > 0
    ]
    key_cols = [col for col in detected.get("key_columns", []) if col in df.columns][:3]
    duplicate_rows = int(df.duplicated(subset=key_cols, keep=False).sum()) if key_cols else int(df.duplicated(keep=False).sum())
    role_map = detected.get("role_map", {})
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "role_counts": {role: len(columns) for role, columns in role_map.items()},
        "missing_top": missing_top,
        "duplicate_row_count": duplicate_rows,
        "key_columns": key_cols,
        "sheet_note": "Workbook sheet envanteri icin inspect_workbook_sheets tool'u kullanilabilir.",
    }


def _overall_metrics(df: pd.DataFrame, score_cols: list[str], group_cols: list[str]) -> dict:
    score_averages = {}
    low_score_density = {}
    for col in score_cols:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.dropna().empty:
            continue
        score_averages[col] = round(float(numeric.mean()), 3)
        scale_max = float(numeric.max())
        threshold = 2 if scale_max <= 5 else 4
        low_score_density[col] = round(float((numeric <= threshold).mean() * 100), 2)
    sorted_scores = sorted(score_averages.items(), key=lambda item: item[1])
    group_count = 0
    if group_cols:
        group_count = int(df[group_cols[0]].dropna().astype(str).nunique())
    return {
        "response_count": int(len(df)),
        "group_count": group_count,
        "overall_score": round(sum(score_averages.values()) / len(score_averages), 3) if score_averages else None,
        "score_averages": score_averages,
        "lowest_score_columns": [{"column": col, "mean": value} for col, value in sorted_scores[:5]],
        "highest_score_columns": [{"column": col, "mean": value} for col, value in reversed(sorted_scores[-5:])],
        "low_score_density_percent": low_score_density,
    }


def _executive_summary(overall: dict, interpretation: dict, detected: dict) -> dict:
    risks = interpretation.get("risk_columns", [])
    strengths = interpretation.get("strength_columns", [])
    bullets = [
        f"Toplam {overall.get('response_count', 0)} yanit / kayit analiz edildi.",
        f"Genel skor {overall.get('overall_score')} seviyesinde." if overall.get("overall_score") is not None else "Genel skor hesaplanamadi.",
    ]
    if overall.get("group_count"):
        bullets.append(f"{overall['group_count']} grup kirilimi tespit edildi.")
    if risks:
        bullets.append(f"Oncelikli gelisim alani: {risks[0]['column']} ({risks[0]['mean']}).")
    if strengths:
        bullets.append(f"Guclu alan: {strengths[0]['column']} ({strengths[0]['mean']}).")
    return {
        "summary_bullets": bullets[:4],
        "critical_findings": _critical_findings(overall, interpretation, detected),
        "standard_sections": [
            "GENEL OZET",
            "KRITIK BULGULAR",
            "GUCLU ALANLAR",
            "RISKLI / GELISIME ACIK ALANLAR",
            "AKSIYON ONERILERI",
            "GRAFIK VE RAPORLAR",
            "KAPANIS",
        ],
    }


def _critical_findings(overall: dict, interpretation: dict, detected: dict) -> list[str]:
    findings = []
    for item in overall.get("lowest_score_columns", [])[:3]:
        findings.append(f"{item['column']} dusuk skor alani olarak izlenmeli ({item['mean']}).")
    if detected.get("comment_columns"):
        findings.append("Acik uclu yorum kolonlari bulundu; tema analiziyle kok nedenler okunabilir.")
    if detected.get("date_columns"):
        findings.append("Tarih/donem kolonu bulundu; trend veya donem karsilastirmasi yapilabilir.")
    if not findings:
        findings.append("Skor veya yorum kolonu net tespit edilemedi; kolon secimi netlestirilirse analiz derinlesir.")
    return findings[:4]


def _recommended_outputs(score_cols: list[str], group_cols: list[str], comment_cols: list[str], date_cols: list[str]) -> list[str]:
    outputs = ["dataset_profile"]
    if score_cols and group_cols:
        outputs.extend(["group_bar_chart", "score_heatmap"])
    if comment_cols:
        outputs.append("theme_analysis")
    if date_cols and score_cols:
        outputs.append("trend_analysis")
    if score_cols:
        outputs.append("executive_summary")
    return outputs


def _manager_pack(df: pd.DataFrame, overview: dict, group_result: dict | None, comment_result: dict | None) -> dict:
    overall = overview.get("overall_metrics", {})
    interpretation = overview.get("interpretation", {})
    lowest_groups = (group_result or {}).get("lowest_groups", [])[:5]
    highest_groups = (group_result or {}).get("highest_groups", [])[:5]
    theme_counts = (comment_result or {}).get("theme_counts", {})
    actions = []
    for item in overall.get("lowest_score_columns", [])[:3]:
        actions.append({
            "timeframe": "0-30 gun",
            "topic": item["column"],
            "recommended_action": "Ilgili grup ve yorum kirilimiyla kok neden oturumu yap.",
            "success_metric": "Takip olcumunde dusuk skor yogunlugunu azalt.",
        })
    for theme, count in list(theme_counts.items())[:3]:
        actions.append({
            "timeframe": "30-60 gun",
            "topic": theme,
            "recommended_action": f"{count} yorumda gecen temaya sahipli aksiyon tanimla.",
            "success_metric": "Aksiyon sahibi, hedef tarih ve iletisim mesaji netlessin.",
        })
    return {
        "dataset_profile": overview.get("dataset_profile", {}),
        "overall_metrics": overall,
        "executive_summary": overview.get("executive_summary", {}),
        "strengths": {
            "score_columns": interpretation.get("strength_columns", []),
            "groups": highest_groups,
            "themes": (comment_result or {}).get("positive_themes", []),
        },
        "risks": {
            "score_columns": interpretation.get("risk_columns", []),
            "groups": lowest_groups,
            "themes": (comment_result or {}).get("negative_themes", []),
            "low_score_density_percent": overall.get("low_score_density_percent", {}),
        },
        "theme_analysis": comment_result or {},
        "action_plan": {
            "actions": actions or [{
                "timeframe": "30-60 gun",
                "topic": "Genel takip",
                "recommended_action": "Sonuclari liderlerle paylas ve takip metriklerini belirle.",
                "success_metric": "Aksiyon plani yayinlanmis olsun.",
            }]
        },
        "generated_outputs_recommended": overview.get("recommended_outputs", []),
    }


survey_analysis_service = SurveyAnalysisService()
