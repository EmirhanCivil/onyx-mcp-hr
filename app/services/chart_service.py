"""Professional chart generation service."""

from __future__ import annotations

from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

from app.config import settings


# Brand palette — HTML rapor ile aynı renkler
_BRAND_PRIMARY = "#0F766E"
_BRAND_PRIMARY_DARK = "#134E4A"
_BRAND_ACCENT = "#F59E0B"
_BRAND_INK = "#0F172A"
_BRAND_INK_SOFT = "#475569"
_BRAND_GRID = "#E2E8F0"
_BRAND_BG = "#FFFFFF"
_HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    "brand_div",
    ["#DC2626", "#F59E0B", "#FACC15", "#65A30D", "#0F766E"],
)


def _apply_chart_style() -> None:
    """Brand-uyumlu seaborn + matplotlib stil presetleri."""
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    plt.rcParams.update({
        "figure.facecolor": _BRAND_BG,
        "axes.facecolor": _BRAND_BG,
        "axes.edgecolor": _BRAND_GRID,
        "axes.labelcolor": _BRAND_INK_SOFT,
        "axes.titlecolor": _BRAND_INK,
        "axes.titleweight": "bold",
        "axes.titlesize": 16,
        "axes.titlepad": 20,
        "axes.labelsize": 11.5,
        "axes.labelweight": "500",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": _BRAND_GRID,
        "grid.linewidth": 0.7,
        "grid.alpha": 0.6,
        "xtick.color": _BRAND_INK_SOFT,
        "ytick.color": _BRAND_INK_SOFT,
        "xtick.labelsize": 10.5,
        "ytick.labelsize": 10.5,
        "font.size": 11,
        "legend.frameon": False,
        "legend.fontsize": 10.5,
        "savefig.facecolor": _BRAND_BG,
        "savefig.edgecolor": "none",
    })
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

    def score_radar(
        self,
        file_id: str,
        group_col: str,
        score_columns_csv: str,
        chart_title: str = "",
        top_n: int = 6,
    ) -> dict:
        df = file_registry.get_frame(file_id)
        score_cols = parse_columns(score_columns_csv)
        require_columns(df, [group_col] + score_cols)
        pivot = self._score_pivot(df, group_col, score_cols, top_n)
        if pivot.empty or len(pivot.columns) < 3:
            return _empty_chart_result("score_radar", "Radar için en az 3 skor boyutu ve grup gerekli.")
        title = chart_title or f"{group_col} — Skor Profili (Radar)"
        path = self._save_radar(pivot, title, "score_radar")
        chart = _chart_output(
            path,
            "Skor Radar",
            "Bu radar grafiği grupların çok boyutlu skor profilini yan yana karşılaştırır.",
        )
        return {"chart_path": path, "chart": chart, "groups": list(pivot.index), "warnings": _verify_output(path)}

    def period_delta_chart(
        self,
        file_id_a: str,
        file_id_b: str,
        group_col: str,
        score_columns_csv: str,
        chart_title: str = "",
        top_n: int = 12,
    ) -> dict:
        df_a = file_registry.get_frame(file_id_a)
        df_b = file_registry.get_frame(file_id_b)
        score_cols = parse_columns(score_columns_csv)
        require_columns(df_a, [group_col] + score_cols)
        require_columns(df_b, [group_col] + score_cols)
        pivot_a = self._score_pivot(df_a, group_col, score_cols, top_n)
        pivot_b = self._score_pivot(df_b, group_col, score_cols, top_n)
        common = pivot_a.index.intersection(pivot_b.index)
        if len(common) < 2:
            return _empty_chart_result("period_delta", "İki dönemde ortak grup yok, delta üretilemedi.")
        delta = (pivot_b.loc[common].mean(axis=1) - pivot_a.loc[common].mean(axis=1)).sort_values()
        title = chart_title or f"{group_col} — Dönem Skor Değişimi (Δ)"
        path = self._save_period_delta(delta, title, "period_delta")
        chart = _chart_output(
            path,
            "Dönem Skor Değişimi",
            "Yeşil çubuklar iyileşmeyi, kırmızı çubuklar kötüleşmeyi gösterir.",
        )
        return {
            "chart_path": path,
            "chart": chart,
            "groups": list(delta.index),
            "deltas": {str(k): float(v) for k, v in delta.items()},
            "warnings": _verify_output(path),
        }

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
        _apply_chart_style()
        output = _chart_path(filename)
        height = max(5.5, min(12, len(data) * 0.5 + 3))
        fig, ax = plt.subplots(figsize=(12, height))
        sns.barplot(data=data, x=y_col, y=x_col, color=_BRAND_PRIMARY, ax=ax,
                    edgecolor=_BRAND_PRIMARY_DARK, linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel(y_col)
        ax.set_ylabel("")
        ax.grid(axis="x", color=_BRAND_GRID, linewidth=0.7, alpha=0.7)
        ax.grid(axis="y", visible=False)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.2f", padding=5, fontsize=9.5,
                         color=_BRAND_INK, weight="600")
        sns.despine(left=True, bottom=True)
        plt.tight_layout()
        fig.savefig(output, dpi=220, bbox_inches="tight")
        plt.close(fig)
        return str(output.resolve())

    def _save_count_bar(self, data: pd.DataFrame, label_col: str, title: str, filename: str) -> str:
        _apply_chart_style()
        output = _chart_path(filename)
        height = max(5.5, min(12, len(data) * 0.5 + 3))
        fig, ax = plt.subplots(figsize=(12, height))
        sns.barplot(data=data, x="count", y=label_col, color=_BRAND_ACCENT, ax=ax,
                    edgecolor="#B45309", linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel("Kayıt Sayısı")
        ax.set_ylabel("")
        ax.grid(axis="x", color=_BRAND_GRID, linewidth=0.7, alpha=0.7)
        ax.grid(axis="y", visible=False)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.0f", padding=5, fontsize=9.5,
                         color=_BRAND_INK, weight="600")
        sns.despine(left=True, bottom=True)
        plt.tight_layout()
        fig.savefig(output, dpi=220, bbox_inches="tight")
        plt.close(fig)
        return str(output.resolve())

    def _save_heatmap(self, data: pd.DataFrame, title: str, filename: str) -> str:
        _apply_chart_style()
        output = _chart_path(filename)
        width = max(10, min(18, len(data.columns) * 1.6 + 4))
        height = max(6, min(14, len(data) * 0.55 + 3))
        fig, ax = plt.subplots(figsize=(width, height))
        sns.heatmap(
            data, annot=True, fmt=".2f", cmap=_HEATMAP_CMAP,
            linewidths=1.2, linecolor=_BRAND_BG,
            cbar_kws={"label": "Ortalama Skor", "shrink": 0.85, "pad": 0.02},
            annot_kws={"fontsize": 10.5, "weight": "600", "color": _BRAND_INK},
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("Skor Boyutu")
        ax.set_ylabel("Grup")
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        plt.setp(ax.get_yticklabels(), rotation=0)
        plt.tight_layout()
        fig.savefig(output, dpi=220, bbox_inches="tight")
        plt.close(fig)
        return str(output.resolve())


    def _save_radar(self, pivot: pd.DataFrame, title: str, filename: str) -> str:
        _apply_chart_style()
        import numpy as np
        output = _chart_path(filename)
        categories = list(pivot.columns)
        n_axes = len(categories)
        angles = np.linspace(0, 2 * np.pi, n_axes, endpoint=False).tolist()
        angles += angles[:1]
        fig = plt.figure(figsize=(10, 9))
        ax = fig.add_subplot(111, projection="polar")
        palette = ["#0F766E", "#F59E0B", "#2563EB", "#DC2626", "#7C3AED", "#65A30D", "#EC4899", "#0EA5E9"]
        max_val = float(pivot.values.max() or 5)
        ax.set_ylim(0, max_val * 1.05)
        for i, (group, row) in enumerate(pivot.iterrows()):
            values = row.tolist() + row.tolist()[:1]
            color = palette[i % len(palette)]
            ax.plot(angles, values, color=color, linewidth=2.4, label=str(group))
            ax.fill(angles, values, color=color, alpha=0.18)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10.5, color=_BRAND_INK_SOFT)
        ax.tick_params(axis="y", labelsize=9, colors=_BRAND_INK_SOFT)
        ax.set_rlabel_position(180 / max(1, n_axes))
        ax.grid(color=_BRAND_GRID, linewidth=0.7, alpha=0.85)
        ax.spines["polar"].set_color(_BRAND_GRID)
        ax.set_title(title, color=_BRAND_INK, fontsize=15, weight="bold", pad=24)
        ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.05), frameon=False, fontsize=10)
        plt.tight_layout()
        fig.savefig(output, dpi=220, bbox_inches="tight")
        plt.close(fig)
        return str(output.resolve())

    def _save_period_delta(self, delta: pd.Series, title: str, filename: str) -> str:
        _apply_chart_style()
        output = _chart_path(filename)
        height = max(5, min(13, len(delta) * 0.55 + 3))
        fig, ax = plt.subplots(figsize=(11, height))
        colors = ["#16A34A" if v >= 0 else "#DC2626" for v in delta.values]
        ax.barh(range(len(delta)), delta.values, color=colors,
                edgecolor=[("#15803D" if v >= 0 else "#B91C1C") for v in delta.values], linewidth=0.7)
        ax.axvline(0, color=_BRAND_INK, linewidth=1.1, alpha=0.7)
        ax.set_yticks(range(len(delta)))
        ax.set_yticklabels([str(idx).replace("\n", " ") for idx in delta.index])
        ax.set_xlabel("Δ Ortalama Skor (B − A)")
        ax.set_title(title)
        ax.grid(axis="x", color=_BRAND_GRID, linewidth=0.7, alpha=0.7)
        ax.grid(axis="y", visible=False)
        for i, v in enumerate(delta.values):
            ax.text(v, i, f"  {v:+.2f}", va="center",
                    ha="left" if v >= 0 else "right", fontsize=10, weight="600",
                    color=("#15803D" if v >= 0 else "#B91C1C"))
        sns.despine(left=True, bottom=True)
        plt.tight_layout()
        fig.savefig(output, dpi=220, bbox_inches="tight")
        plt.close(fig)
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


_PUBLIC_FILES_BASE = "http://localhost:8007"


def _to_public_url(local_path: str) -> str:
    p = (local_path or "").replace("\\", "/")
    if "/app/data/outputs/" in p:
        return p.replace("/app/data/outputs", _PUBLIC_FILES_BASE)
    return local_path


def _chart_output(path: str, title: str, description: str) -> dict:
    url = _to_public_url(path)
    return {
        "type": "chart",
        "title": title,
        "description": description,
        "format": "png",
        "path": path,
        "url": url,
        "public_url": url,
        "markdown": f"![{title}]({url})",
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
