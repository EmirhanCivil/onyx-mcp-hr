"""MCP tools for HR survey analysis."""

from __future__ import annotations

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.chart_service import chart_service
from app.services.excel_service import excel_service
from app.services.report_service import report_service
from app.services.survey_analysis_service import survey_analysis_service


def register_survey_tools(mcp: FastMCP) -> None:
    """Register survey overview, group, comment, and period comparison tools."""

    @mcp.tool()
    def auto_analyze_survey(file_query: str = "", include_comments: bool = True, include_outputs: bool = True) -> str:
        """File_id istemeden uygun anket/genel survey dosyasini analiz eder, grafik ve rapor uretir."""

        def run():
            excel_service.scan_uploads()
            selected = excel_service.select_file(file_query, "survey")
            if not selected:
                return ok_response(
                    "auto_analyze_survey",
                    "Uygun anket dosyası bulunamadı.",
                    {"file_query": file_query},
                    warnings=["Anket Excel/CSV dosyasını data/uploads/survey klasörüne koyun."],
                )
            overview = survey_analysis_service.overview(selected["file_id"])
            data = {"selected_file": selected, "overview": overview}
            outputs = []
            files = []
            charts = []
            recommended = overview.get("recommended_group_analysis")
            if recommended:
                data["group_analysis"] = survey_analysis_service.by_group(
                    selected["file_id"],
                    recommended["group_col"],
                    ",".join(recommended["score_columns"]),
                )
            comments = overview.get("recommended_comment_columns", [])
            if include_comments and comments:
                data["comment_analysis"] = survey_analysis_service.comments(selected["file_id"], ",".join(comments))
            data["manager_pack"] = survey_analysis_service.executive_summary(selected["file_id"], include_comments)
            warnings = []
            if include_outputs:
                visual_pack = chart_service.auto_survey_charts(selected["file_id"])
                data["visual_pack"] = visual_pack
                outputs.extend(visual_pack.get("charts", []))
                charts.extend(item["path"] for item in visual_pack.get("charts", []))
                files.extend(charts)
                report = report_service.create_survey_report(
                    overview,
                    data.get("group_analysis"),
                    data.get("comment_analysis"),
                    ["html", "markdown"],
                    visual_pack.get("charts", []),
                )
                data["report"] = {"summary_markdown": report.get("summary_markdown")}
                outputs.extend(report.get("generated_outputs", []))
                files.extend(report.get("files", []))
                warnings.extend(visual_pack.get("warnings", []))
            return ok_response(
                "auto_analyze_survey",
                "Otomatik anket analizi tamamlandı.",
                data,
                files=list(dict.fromkeys(files)),
                charts=list(dict.fromkeys(charts)),
                generated_outputs=outputs,
                warnings=list(dict.fromkeys(warnings)),
            )

        return tool_handler("auto_analyze_survey", run)

    @mcp.tool()
    def analyze_survey_overview(file_id: str) -> str:
        """Yuklu anket dosyasinin kolonlarini algilar ve sayisal genel ozet uretir."""

        return tool_handler(
            "analyze_survey_overview",
            lambda: ok_response("analyze_survey_overview", "Anket genel analizi tamamlandi.", survey_analysis_service.overview(file_id)),
        )

    @mcp.tool()
    def analyze_survey_numeric(file_id: str, columns: str) -> str:
        """Secili sayisal anket kolonlari icin ortalama, medyan, min, max, std hesaplar."""

        return tool_handler(
            "analyze_survey_numeric",
            lambda: ok_response("analyze_survey_numeric", "Sayisal analiz tamamlandi.", survey_analysis_service.numeric(file_id, columns)),
        )

    @mcp.tool()
    def analyze_survey_by_group(file_id: str, group_col: str, score_columns: str, min_group_size: int = 5) -> str:
        """Anket skorlarini birim/departman/lokasyon gibi kirilimlara gore analiz eder."""

        return tool_handler(
            "analyze_survey_by_group",
            lambda: ok_response(
                "analyze_survey_by_group",
                "Grup bazli analiz tamamlandi.",
                survey_analysis_service.by_group(file_id, group_col, score_columns, min_group_size),
            ),
        )

    @mcp.tool()
    def analyze_survey_comments(file_id: str, comment_columns: str) -> str:
        """Acik uclu yorumlari tema ve basit duygu kirilimina gore ozetler."""

        return tool_handler(
            "analyze_survey_comments",
            lambda: ok_response("analyze_survey_comments", "Yorum tema analizi tamamlandi.", survey_analysis_service.comments(file_id, comment_columns)),
        )

    @mcp.tool()
    def create_survey_executive_summary(file_id: str, include_comments: bool = True) -> str:
        """Anket icin yonetici ozeti, guclu/riskli alanlar ve aksiyon paketi uretir."""

        return tool_handler(
            "create_survey_executive_summary",
            lambda: ok_response(
                "create_survey_executive_summary",
                "Yonetici ozeti hazirlandi.",
                survey_analysis_service.executive_summary(file_id, include_comments),
            ),
        )

    @mcp.tool()
    def compare_survey_periods(
        file_id_a: str,
        file_id_b: str,
        group_col: str,
        score_columns: str,
        min_group_size: int = 5,
    ) -> str:
        """Iki anket donemini departman/birim bazli skor degisimi acisindan karsilastirir."""

        return tool_handler(
            "compare_survey_periods",
            lambda: ok_response(
                "compare_survey_periods",
                "Donem karsilastirmasi tamamlandi.",
                survey_analysis_service.compare_periods(file_id_a, file_id_b, group_col, score_columns, min_group_size),
            ),
        )
