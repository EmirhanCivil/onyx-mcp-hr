"""Report generation service."""

from __future__ import annotations

from app.exporters.docx_exporter import export_docx
from app.exporters.html_exporter import export_html
from app.exporters.json_exporter import export_json
from app.exporters.markdown_exporter import export_markdown
from app.services.summary_service import (
    build_candidate_pool_summary,
    build_data_quality_summary,
    build_department_risk_summary,
    build_shortlist_summary,
    build_survey_executive_summary,
)


class ReportService:
    """Creates Markdown, HTML, DOCX, and JSON reports from analysis payloads."""

    def create_survey_report(
        self,
        overview: dict,
        group_analysis: dict | None = None,
        comment_analysis: dict | None = None,
        formats: list[str] | None = None,
        chart_outputs: list[dict] | None = None,
    ) -> dict:
        selected = formats or ["markdown", "html"]
        content = build_survey_executive_summary(overview, group_analysis, comment_analysis)
        files: list[str] = []
        outputs: list[dict] = []
        if "markdown" in selected:
            path = export_markdown(content, "survey_executive_report")
            files.append(path)
            outputs.append(_report_output(path, "Yönetici Raporu", "Markdown yönetici özeti.", "md", "text/markdown"))
        if "html" in selected:
            path = export_html("Yönetici Raporu", content, "survey_executive_report")
            files.append(path)
            outputs.append(_report_output(path, "Yönetici Raporu", "Profesyonel HTML yönetici raporu.", "html", "text/html"))
        if "docx" in selected:
            path = export_docx("Yönetici Raporu", [("Yönetici Özeti", content)], "survey_executive_report")
            files.append(path)
            outputs.append(_report_output(path, "Yönetici Raporu", "DOCX yönetici raporu.", "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        if "json" in selected:
            path = export_json({
                "overview": overview,
                "group_analysis": group_analysis,
                "comment_analysis": comment_analysis,
            }, "survey_analysis_payload")
            files.append(path)
            outputs.append(_report_output(path, "Analiz Verisi", "Kontrollü analiz payload dosyası.", "json", "application/json", display=False))
        if chart_outputs:
            outputs.extend(chart_outputs)
        return {"summary_markdown": content, "files": files, "generated_outputs": outputs}

    def create_candidate_pool_report(self, pool: dict, formats: list[str] | None = None) -> dict:
        selected = formats or ["markdown", "html"]
        content = build_candidate_pool_summary(pool)
        files: list[str] = []
        outputs: list[dict] = []
        title = "Aday Havuzu Raporu"
        if "markdown" in selected:
            path = export_markdown(content, "candidate_pool_report")
            files.append(path)
            outputs.append(_report_output(path, title, "Markdown aday havuzu raporu.", "md", "text/markdown"))
        if "html" in selected:
            path = export_html(title, content, "candidate_pool_report")
            files.append(path)
            outputs.append(_report_output(path, title, "HTML aday havuzu raporu.", "html", "text/html"))
        if "docx" in selected:
            path = export_docx(title, [("Yonetici Ozeti", content)], "candidate_pool_report")
            files.append(path)
            outputs.append(
                _report_output(
                    path,
                    title,
                    "DOCX aday havuzu raporu.",
                    "docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            )
        return {"summary_markdown": content, "files": files, "generated_outputs": outputs}

    def create_shortlist_report(self, shortlist: dict, formats: list[str] | None = None) -> dict:
        selected = formats or ["markdown", "html"]
        content = build_shortlist_summary(shortlist)
        files: list[str] = []
        outputs: list[dict] = []
        title = "Shortlist Raporu"
        if "markdown" in selected:
            path = export_markdown(content, "shortlist_report")
            files.append(path)
            outputs.append(_report_output(path, title, "Markdown shortlist raporu.", "md", "text/markdown"))
        if "html" in selected:
            path = export_html(title, content, "shortlist_report")
            files.append(path)
            outputs.append(_report_output(path, title, "HTML shortlist raporu.", "html", "text/html"))
        if "docx" in selected:
            path = export_docx(title, [("Shortlist", content)], "shortlist_report")
            files.append(path)
            outputs.append(
                _report_output(
                    path,
                    title,
                    "DOCX shortlist raporu.",
                    "docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            )
        return {"summary_markdown": content, "files": files, "generated_outputs": outputs}

    def create_data_quality_report(self, audit: dict, formats: list[str] | None = None) -> dict:
        selected = formats or ["markdown", "html"]
        content = build_data_quality_summary(audit)
        files: list[str] = []
        outputs: list[dict] = []
        title = "Veri Kalite Raporu"
        if "markdown" in selected:
            path = export_markdown(content, "data_quality_report")
            files.append(path)
            outputs.append(_report_output(path, title, "Markdown veri kalite raporu.", "md", "text/markdown"))
        if "html" in selected:
            path = export_html(title, content, "data_quality_report")
            files.append(path)
            outputs.append(_report_output(path, title, "HTML veri kalite raporu.", "html", "text/html"))
        if "docx" in selected:
            path = export_docx(title, [("Veri Kalite Ozeti", content)], "data_quality_report")
            files.append(path)
            outputs.append(
                _report_output(
                    path,
                    title,
                    "DOCX veri kalite raporu.",
                    "docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            )
        return {"summary_markdown": content, "files": files, "generated_outputs": outputs}

    def create_department_risk_report(self, overview: dict, group_analysis: dict | None = None, formats: list[str] | None = None) -> dict:
        selected = formats or ["markdown", "html"]
        content = build_department_risk_summary(overview, group_analysis)
        files: list[str] = []
        outputs: list[dict] = []
        title = "Departman Risk Raporu"
        if "markdown" in selected:
            path = export_markdown(content, "department_risk_report")
            files.append(path)
            outputs.append(_report_output(path, title, "Markdown departman risk raporu.", "md", "text/markdown"))
        if "html" in selected:
            path = export_html(title, content, "department_risk_report")
            files.append(path)
            outputs.append(_report_output(path, title, "HTML departman risk raporu.", "html", "text/html"))
        if "docx" in selected:
            path = export_docx(title, [("Departman Risk Ozeti", content)], "department_risk_report")
            files.append(path)
            outputs.append(
                _report_output(
                    path,
                    title,
                    "DOCX departman risk raporu.",
                    "docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            )
        return {"summary_markdown": content, "files": files, "generated_outputs": outputs}


def _report_output(path: str, title: str, description: str, fmt: str, mime_type: str, display: bool = True) -> dict:
    return {
        "type": "report",
        "title": title,
        "description": description,
        "format": fmt,
        "path": path,
        "mime_type": mime_type,
        "display": display,
    }


report_service = ReportService()
