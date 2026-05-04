"""MCP report generation tools."""

from __future__ import annotations

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.chart_service import chart_service
from app.services.report_service import report_service
from app.services.survey_analysis_service import survey_analysis_service
from app.services.candidate_pool_service import candidate_pool_service
from app.services.excel_service import excel_service
from app.services.hr_service import hr_service


def register_report_tools(mcp: FastMCP) -> None:
    """Register report tools."""

    @mcp.tool()
    def create_survey_report(
        file_id: str,
        group_col: str = "",
        score_columns: str = "",
        comment_columns: str = "",
        formats: str = "markdown,html",
        include_charts: bool = True,
    ) -> str:
        """Anket/genel skor dosyası için profesyonel yönetici raporu üretir."""

        def run():
            overview = survey_analysis_service.overview(file_id)
            recommended = overview.get("recommended_group_analysis", {})
            resolved_group = group_col or recommended.get("group_col", "")
            resolved_scores = score_columns or ",".join(recommended.get("score_columns", []))
            resolved_comments = comment_columns or ",".join(overview.get("recommended_comment_columns", []))
            group = survey_analysis_service.by_group(file_id, resolved_group, resolved_scores) if resolved_group and resolved_scores else None
            comments = survey_analysis_service.comments(file_id, resolved_comments) if resolved_comments else None
            chart_outputs = []
            chart_paths = []
            chart_warnings = []
            if include_charts:
                visuals = chart_service.auto_survey_charts(file_id)
                chart_outputs = visuals.get("charts", [])
                chart_paths = [item["path"] for item in chart_outputs]
                chart_warnings = visuals.get("warnings", [])
            selected = [part.strip().lower() for part in formats.split(",") if part.strip()]
            data = report_service.create_survey_report(overview, group, comments, selected, chart_outputs)
            files = data.get("files", []) + chart_paths
            return ok_response(
                "create_survey_report",
                "Rapor oluşturuldu.",
                data,
                files=files,
                charts=chart_paths,
                generated_outputs=data.get("generated_outputs", []),
                warnings=chart_warnings,
            )

        return tool_handler("create_survey_report", run)

    @mcp.tool()
    def create_candidate_pool_report(
        file_query: str = "",
        file_id: str = "",
        formats: str = "markdown,html",
        include_export_pack: bool = False,
    ) -> str:
        """Aday havuzu raporu (Markdown/HTML/DOCX) uretir; opsiyonel export paketi ekler."""

        def run():
            pool = candidate_pool_service.analyze(file_query=file_query, file_id=file_id, limit=20, export=include_export_pack)
            selected = [part.strip().lower() for part in formats.split(",") if part.strip()]
            report = report_service.create_candidate_pool_report(pool.get("data", {}), selected)
            files = (pool.get("files", []) or []) + (report.get("files", []) or [])
            outputs = (pool.get("generated_outputs", []) or []) + (report.get("generated_outputs", []) or [])
            return ok_response(
                "create_candidate_pool_report",
                "Aday havuzu raporu olusturuldu.",
                {"summary_markdown": report.get("summary_markdown"), "pool": pool.get("data", {})},
                files=list(dict.fromkeys(files)),
                generated_outputs=outputs,
            )

        return tool_handler("create_candidate_pool_report", run)

    @mcp.tool()
    def create_shortlist_report(
        role: str,
        required_skills: str = "",
        preferred_skills: str = "",
        query: str = "",
        limit: int = 10,
        anonymize: bool = False,
        formats: str = "markdown,html",
    ) -> str:
        """Pozisyon bazli shortlist raporu (Markdown/HTML/DOCX) uretir."""

        def run():
            shortlist = hr_service.candidate_shortlist(role, required_skills, preferred_skills, query, limit, anonymize, include_snippets=False)
            selected = [part.strip().lower() for part in formats.split(",") if part.strip()]
            report = report_service.create_shortlist_report(shortlist, selected)
            files = report.get("files", []) or []
            outputs = report.get("generated_outputs", []) or []
            return ok_response(
                "create_shortlist_report",
                "Shortlist raporu olusturuldu.",
                {"summary_markdown": report.get("summary_markdown"), "shortlist": shortlist},
                files=files,
                generated_outputs=outputs,
            )

        return tool_handler("create_shortlist_report", run)

    @mcp.tool()
    def create_data_quality_report(
        file_query: str = "",
        file_id: str = "",
        category: str = "spreadsheet",
        formats: str = "markdown,html",
    ) -> str:
        """Veri kalite raporu (Markdown/HTML/DOCX) uretir."""

        def run():
            excel_service.scan_uploads()
            selected_file = None
            target = file_id
            if not target:
                selected_file = excel_service.select_file(file_query, category)
                target = selected_file["file_id"] if selected_file else ""
            if not target:
                return ok_response(
                    "create_data_quality_report",
                    "Uygun dosya bulunamadi.",
                    {"file_query": file_query, "category": category},
                    warnings=["Dosyayi uploads altina ekleyip refresh_file_library calistirin."],
                )
            audit = excel_service.audit_quality(target)
            if selected_file:
                audit["selected_file"] = selected_file
            selected = [part.strip().lower() for part in formats.split(",") if part.strip()]
            report = report_service.create_data_quality_report(audit, selected)
            files = report.get("files", []) or []
            outputs = report.get("generated_outputs", []) or []
            return ok_response(
                "create_data_quality_report",
                "Veri kalite raporu olusturuldu.",
                {"summary_markdown": report.get("summary_markdown"), "audit": audit},
                files=files,
                generated_outputs=outputs,
            )

        return tool_handler("create_data_quality_report", run)

    @mcp.tool()
    def create_department_risk_report(
        file_query: str = "",
        file_id: str = "",
        group_col: str = "",
        score_columns: str = "",
        formats: str = "markdown,html",
    ) -> str:
        """Anket verisinden departman/grup risk raporu (Markdown/HTML/DOCX) uretir."""

        def run():
            excel_service.scan_uploads()
            selected = None
            target = file_id
            if not target:
                selected = excel_service.select_file(file_query, "survey")
                target = selected["file_id"] if selected else ""
            if not target:
                return ok_response(
                    "create_department_risk_report",
                    "Uygun anket dosyasi bulunamadi.",
                    {"file_query": file_query},
                    warnings=["uploads/survey altina anket dosyasi ekleyin veya file_id verin."],
                )

            overview = survey_analysis_service.overview(target)
            recommended = overview.get("recommended_group_analysis", {}) or {}
            resolved_group = group_col or recommended.get("group_col", "")
            resolved_scores = score_columns or ",".join(recommended.get("score_columns", []))
            group = None
            if resolved_group and resolved_scores:
                group = survey_analysis_service.by_group(target, resolved_group, resolved_scores)
            selected_formats = [part.strip().lower() for part in formats.split(",") if part.strip()]
            report = report_service.create_department_risk_report(overview, group, selected_formats)
            files = report.get("files", []) or []
            outputs = report.get("generated_outputs", []) or []
            data = {
                "summary_markdown": report.get("summary_markdown"),
                "selected_file": selected,
                "overview": overview,
                "group_analysis": group,
            }
            return ok_response(
                "create_department_risk_report",
                "Departman risk raporu olusturuldu.",
                data,
                files=files,
                generated_outputs=outputs,
            )

        return tool_handler("create_department_risk_report", run)
