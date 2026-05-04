"""Professional chart generation service."""

from __future__ import annotations

from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from app.config import settings
from app.core.file_registry import file_registry
from app.utils.column_detector import detect_columns
from app.utils.file_utils import ensure_parent, make_job_id, safe_filename
from app.utils.validation_utils import parse_columns, require_columns


class ChartService:
    """Creates readable chart files from registered DataFrames."""

    def group_bar_chart(
        self,
        file_id: str,
        group_col: str,
        value_col: str,
        chart_title: str = "",
        top_n: int = 15,
    ) -> dict:
        df = file_registry.get_frame(file_id)
        require_columns(df, [group_col, value_col])
        grouped = self._group_mean(df, group_col, value_col, top_n)
        if grouped.empty:
            return _empty_chart_result("group_bar", "Grafik için yeterli veri bulunamadı.")
        title = chart_title or f"{group_col} Bazında Ortalama {value_col}"
        path = self._save_bar(grouped, group_col, value_col, title, "group_average_score")
        chart = _chart_output(
            path,
            "Grup Bazında Ortalama Skor",
            "Bu grafik gruplar arasındaki ortalama skor farklarını gösterir.",
        )
        return {"chart_path": path, "chart": chart, "rows_charted": int(len(grouped)), "warnings": _verify_output(path)}

    def score_heatmap(self, file_id: str, group_col: str, score_columns_csv: str, chart_title: str = "", top_n: int = 20) -> dict:
        df = file_registry.get_frame(file_id)
        score_cols = parse_columns(score_columns_csv)
        require_columns(df, [group_col] + score_cols)
        pivot = self._score_pivot(df, group_col, score_cols, top_n)
        if pivot.empty:
            return _empty_chart_result("score_heatmap", "Heatmap için yeterli skor verisi bulunamadı.")
        title = chart_title or "Grup ve Skor Boyutu Isı Haritası"
        path = self._save_heatmap(pivot, title, "score_heatmap")
        chart = _chart_output(
            path,
            "Skor Isı Haritası",
            "Bu heatmap hangi grubun hangi skor boyutunda güçlü veya zayıf olduğunu gösterir.",
        )
        return {"chart_path": path, "chart": chart, "group_count": int(len(pivot)), "score_columns": score_cols, "warnings": _verify_output(path)}

    def category_distribution_chart(self, file_id: str, category_col: str, chart_title: str = "", top_n: int = 15) -> dict:
        df = file_registry.get_frame(file_id)
        require_columns(df, [category_col])
        counts = _top_counts(df[category_col], top_n)
        if counts.empty or len(counts) < 2:
            return _empty_chart_result("category_distribution", "Bu kolon için anlamlı kategori grafiği üretilemedi.")
        title = chart_title or f"{category_col} Dağılımı"
        path = self._save_count_bar(counts, category_col, title, "category_distribution")
        chart = _chart_output(
            path,
            "Kategori Dağılımı",
            "Bu grafik seçili kategorideki kayıt dağılımını gösterir.",
        )
        return {"chart_path": path, "chart": chart, "rows_charted": int(len(counts)), "warnings": _verify_output(path)}

    def auto_survey_charts(self, file_id: str, top_n: int = 15) -> dict:
        df = file_registry.get_frame(file_id)
        detected = detect_columns(df)
        outputs = []
        warnings = []
        group_cols = detected.get("group_columns", [])
        score_cols = detected.get("likely_score_columns", [])
        category_cols = detected.get("categorical_columns", [])

        if group_cols and score_cols:
            group_col = group_cols[0]
            first_score = score_cols[0]
            bar = self.group_bar_chart(file_id, group_col, first_score, top_n=top_n)
            outputs.extend(_extract_chart(bar))
            warnings.extend(bar.get("warnings", []))
            if len(score_cols) >= 2:
                heatmap = self.score_heatmap(file_id, group_col, ",".join(score_cols[:8]), top_n=top_n)
                outputs.extend(_extract_chart(heatmap))
                warnings.extend(heatmap.get("warnings", []))
        elif score_cols:
            warnings.append("Grup kolonu bulunamadığı için grup bazlı grafik üretilemedi.")

        for col in category_cols[:2]:
            if col not in group_cols:
                category = self.category_distribution_chart(file_id, col, top_n=top_n)
                outputs.extend(_extract_chart(category))
                warnings.extend(category.get("warnings", []))

        return {
            "analysis_type": "survey_visuals",
            "detected_columns": detected,
            "charts": outputs,
            "chart_count": len(outputs),
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _group_mean(self, df: pd.DataFrame, group_col: str, value_col: str, top_n: int) -> pd.DataFrame:
        work = df[[group_col, value_col]].copy()
        work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
        work = work.dropna(subset=[value_col])
        grouped = (
            work.groupby(group_col, dropna=False)[value_col]
            .mean()
            .sort_values(ascending=False)
            .head(max(3, min(top_n, 30)))
            .reset_index()
        )
        grouped[group_col] = grouped[group_col].fillna("Boş").astype(str).map(_wrap_label)
        return grouped

    def _score_pivot(self, df: pd.DataFrame, group_col: str, score_cols: list[str], top_n: int) -> pd.DataFrame:
        work = df[[group_col] + score_cols].copy()
        for col in score_cols:
            work[col] = pd.to_numeric(work[col], errors="coerce")
        counts = work[group_col].fillna("Boş").astype(str).value_counts().head(max(3, min(top_n, 30))).index
        work[group_col] = work[group_col].fillna("Boş").astype(str)
        work = work[work[group_col].isin(counts)]
        pivot = work.groupby(group_col)[score_cols].mean().round(2)
        pivot.index = [_wrap_label(item, 22) for item in pivot.index]
        pivot.columns = [_wrap_label(item, 16) for item in pivot.columns]
        return pivot

    def _save_bar(self, data: pd.DataFrame, x_col: str, y_col: str, title: str, filename: str) -> str:
        output = _chart_path(filename)
        height = max(5.5, min(12, len(data) * 0.48 + 2.5))
        plt.figure(figsize=(12, height), facecolor="white")
        ax = sns.barplot(data=data, x=y_col, y=x_col, color="#2563EB")
        ax.set_title(title, fontsize=15, weight="bold", pad=18)
        ax.set_xlabel(y_col, fontsize=11)
        ax.set_ylabel("")
        ax.grid(axis="x", alpha=0.18)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.2f", padding=4, fontsize=9)
        sns.despine(left=True, bottom=True)
        plt.tight_layout()
        plt.savefig(output, dpi=220, bbox_inches="tight")
        plt.close()
        return str(output.resolve())

    def _save_count_bar(self, data: pd.DataFrame, label_col: str, title: str, filename: str) -> str:
        output = _chart_path(filename)
        height = max(5.5, min(12, len(data) * 0.48 + 2.5))
        plt.figure(figsize=(12, height), facecolor="white")
        ax = sns.barplot(data=data, x="count", y=label_col, color="#0F766E")
        ax.set_title(title, fontsize=15, weight="bold", pad=18)
        ax.set_xlabel("Kayıt Sayısı", fontsize=11)
        ax.set_ylabel("")
        ax.grid(axis="x", alpha=0.18)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.0f", padding=4, fontsize=9)
        sns.despine(left=True, bottom=True)
        plt.tight_layout()
        plt.savefig(output, dpi=220, bbox_inches="tight")
        plt.close()
        return str(output.resolve())

    def _save_heatmap(self, data: pd.DataFrame, title: str, filename: str) -> str:
        output = _chart_path(filename)
        width = max(10, min(18, len(data.columns) * 1.5 + 4))
        height = max(6, min(14, len(data) * 0.5 + 3))
        plt.figure(figsize=(width, height), facecolor="white")
        ax = sns.heatmap(data, annot=True, fmt=".2f", cmap="RdYlGn", linewidths=0.5, linecolor="white", cbar_kws={"label": "Ortalama"})
        ax.set_title(title, fontsize=15, weight="bold", pad=18)
        ax.set_xlabel("Skor Boyutu", fontsize=11)
        ax.set_ylabel("Grup", fontsize=11)
        plt.xticks(rotation=30, ha="right")
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(output, dpi=220, bbox_inches="tight")
        plt.close()
        return str(output.resolve())


def _chart_path(name: str) -> Path:
    job = make_job_id("chart")
    output = settings.CHART_DIR / job / f"{safe_filename(name)}.png"
    ensure_parent(output)
    return output


def _top_counts(series: pd.Series, top_n: int) -> pd.DataFrame:
    cleaned = series.map(lambda item: "Boş" if pd.isna(item) or str(item).strip() == "" else str(item).strip())
    counts = cleaned.value_counts()
    max_items = max(3, min(top_n, 30))
    top = counts.head(max_items).copy()
    other_count = int(counts.iloc[max_items:].sum())
    if other_count:
        top.loc["Diğer"] = other_count
    result = top.reset_index()
    result.columns = ["category", "count"]
    result["category"] = result["category"].map(_wrap_label)
    return result.rename(columns={"category": series.name or "Kategori"})


def _wrap_label(value: object, width: int = 28) -> str:
    text = str(value)
    return fill(text, width=width, break_long_words=False, replace_whitespace=False)


def _chart_output(path: str, title: str, description: str) -> dict:
    return {
        "type": "chart",
        "title": title,
        "description": description,
        "format": "png",
        "path": path,
        "mime_type": "image/png",
        "display": True,
    }


def _extract_chart(result: dict) -> list[dict]:
    chart = result.get("chart")
    return [chart] if chart else []


def _verify_output(path: str) -> list[str]:
    target = Path(path)
    if not target.exists():
        return ["Grafik dosyası oluşturulamadı."]
    if target.stat().st_size <= 0:
        return ["Grafik dosyası boş görünüyor."]
    return []


def _empty_chart_result(chart_type: str, warning: str) -> dict:
    return {"chart_type": chart_type, "chart_path": "", "chart": None, "warnings": [warning]}


chart_service = ChartService()
