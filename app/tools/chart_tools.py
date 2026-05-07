"""MCP chart generation tools."""

from __future__ import annotations

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.chart_service import chart_service


def register_chart_tools(mcp: FastMCP) -> None:
    """Register chart tools."""

    @mcp.tool()
    def create_group_bar_chart(file_id: str, group_col: str, value_col: str, chart_title: str = "", top_n: int = 15) -> str:
        """Grup/kategori bazında ortalama skor bar grafiği üretir."""

        def run():
            data = chart_service.group_bar_chart(file_id, group_col, value_col, chart_title, top_n)
            outputs = [data["chart"]] if data.get("chart") else []
            chart_paths = [item["path"] for item in outputs]
            return ok_response(
                "create_group_bar_chart",
                "Grafik oluşturuldu.",
                data,
                charts=chart_paths,
                files=chart_paths,
                generated_outputs=outputs,
                warnings=data.get("warnings", []),
            )

        return tool_handler("create_group_bar_chart", run)

    @mcp.tool()
    def create_score_heatmap(file_id: str, group_col: str, score_columns: str, chart_title: str = "", top_n: int = 20) -> str:
        """Grup/kategori x skor kolonları için ısı haritası üretir."""

        def run():
            data = chart_service.score_heatmap(file_id, group_col, score_columns, chart_title, top_n)
            outputs = [data["chart"]] if data.get("chart") else []
            chart_paths = [item["path"] for item in outputs]
            return ok_response(
                "create_score_heatmap",
                "Isı haritası oluşturuldu.",
                data,
                charts=chart_paths,
                files=chart_paths,
                generated_outputs=outputs,
                warnings=data.get("warnings", []),
            )

        return tool_handler("create_score_heatmap", run)

    @mcp.tool()
    def create_category_distribution_chart(file_id: str, category_col: str, chart_title: str = "", top_n: int = 15) -> str:
        """Kategori dağılımı için okunabilir yatay bar grafik üretir."""

        def run():
            data = chart_service.category_distribution_chart(file_id, category_col, chart_title, top_n)
            outputs = [data["chart"]] if data.get("chart") else []
            chart_paths = [item["path"] for item in outputs]
            return ok_response(
                "create_category_distribution_chart",
                "Kategori dağılım grafiği oluşturuldu.",
                data,
                charts=chart_paths,
                files=chart_paths,
                generated_outputs=outputs,
                warnings=data.get("warnings", []),
            )

        return tool_handler("create_category_distribution_chart", run)

    @mcp.tool()
    def create_score_radar(file_id: str, group_col: str, score_columns: str, chart_title: str = "", top_n: int = 6) -> str:
        """[OPT-IN] Premium görsel: top_n grup için çok boyutlu radar/spider chart.
        Default analiz paketine dahil DEĞİL — kullanıcı açıkça istediğinde çağrılır."""

        def run():
            data = chart_service.score_radar(file_id, group_col, score_columns, chart_title, top_n)
            outputs = [data["chart"]] if data.get("chart") else []
            chart_paths = [item["path"] for item in outputs]
            return ok_response(
                "create_score_radar",
                "Radar grafiği oluşturuldu.",
                data,
                charts=chart_paths,
                files=chart_paths,
                generated_outputs=outputs,
                warnings=data.get("warnings", []),
            )

        return tool_handler("create_score_radar", run)

    @mcp.tool()
    def create_period_delta_chart(
        file_id_a: str,
        file_id_b: str,
        group_col: str,
        score_columns: str,
        chart_title: str = "",
        top_n: int = 12,
    ) -> str:
        """[OPT-IN] Premium görsel: iki dönem (A=eski, B=yeni) arasında grup bazlı ortalama skor değişimi —
        diverging bar (yeşil iyileşme / kırmızı kötüleşme). compare_survey_periods'ı tamamlar."""

        def run():
            data = chart_service.period_delta_chart(file_id_a, file_id_b, group_col, score_columns, chart_title, top_n)
            outputs = [data["chart"]] if data.get("chart") else []
            chart_paths = [item["path"] for item in outputs]
            return ok_response(
                "create_period_delta_chart",
                "Dönem delta grafiği oluşturuldu.",
                data,
                charts=chart_paths,
                files=chart_paths,
                generated_outputs=outputs,
                warnings=data.get("warnings", []),
            )

        return tool_handler("create_period_delta_chart", run)

    @mcp.tool()
    def auto_create_survey_visuals(file_id: str, top_n: int = 15) -> str:
        """Algılanan kolonlara göre survey/genel tablo için uygun grafik paketini üretir."""

        def run():
            data = chart_service.auto_survey_charts(file_id, top_n)
            chart_paths = [item["path"] for item in data.get("charts", [])]
            return ok_response(
                "auto_create_survey_visuals",
                "Otomatik grafik paketi oluşturuldu.",
                data,
                charts=chart_paths,
                files=chart_paths,
                generated_outputs=data.get("charts", []),
                warnings=data.get("warnings", []),
            )

        return tool_handler("auto_create_survey_visuals", run)
