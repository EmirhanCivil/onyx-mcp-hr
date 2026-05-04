"""Unified file library tools for Onyx-friendly workflows."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from app.config import settings
from app.core.response_schema import ok_response, tool_handler
from app.services.cv_service import cv_service
from app.services.excel_service import excel_service


def register_library_tools(mcp: FastMCP) -> None:
    """Register tools that remove file-path busywork from chat workflows."""

    @mcp.tool()
    def refresh_file_library() -> str:
        """CV, Excel ve anket klasorlerini bastan tarar."""

        def run():
            spreadsheets = excel_service.scan_uploads()
            cvs = cv_service.scan_cvs()
            return ok_response(
                "refresh_file_library",
                "Dosya kutuphanesi guncellendi.",
                {
                    "folders": _folder_map(),
                    "spreadsheets": spreadsheets,
                    "cvs": cvs,
                },
            )

        return tool_handler("refresh_file_library", run)

    @mcp.tool()
    def list_file_library() -> str:
        """CV, Excel ve anket dosyalarini tek cevapta listeler."""

        def run():
            excel_service.scan_uploads()
            cv_service.scan_cvs()
            return ok_response(
                "list_file_library",
                "Dosya kutuphanesi listelendi.",
                {
                    "folders": _folder_map(),
                    "spreadsheets": excel_service.group_loaded_files(),
                    "cvs": cv_service.list_cvs(),
                },
            )

        return tool_handler("list_file_library", run)

    @mcp.tool()
    def get_system_status() -> str:
        """MCP kurulumunun klasor, dosya ve Onyx baglanti hazirligini ozetler."""

        def run():
            spreadsheet_scan = excel_service.scan_uploads()
            cv_scan = cv_service.scan_cvs()
            folders = _folder_map()
            folder_checks = {
                key: _folder_status(Path(value))
                for key, value in folders.items()
            }
            warnings = []
            if cv_scan["loaded_count"] == 0:
                warnings.append("CV bulunamadi. PDF/DOCX/TXT dosyalarini data/uploads/cv klasorune koyun.")
            if spreadsheet_scan["loaded_count"] == 0:
                warnings.append("Excel/anket dosyasi bulunamadi. Dosyalari data/uploads/excel veya data/uploads/survey klasorune koyun.")
            if any(not status["exists"] for status in folder_checks.values()):
                warnings.append("Eksik klasor var. Container yeniden baslatilirken volume pathlerini kontrol edin.")

            return ok_response(
                "get_system_status",
                "Sistem durumu hazirlandi.",
                {
                    "status": "ready" if not warnings else "needs_attention",
                    "endpoint": {
                        "container_url": f"http://{settings.MCP_HOST}:{settings.MCP_PORT}{settings.MCP_PATH}",
                        "default_host_url": f"http://localhost:{settings.MCP_PORT}{settings.MCP_PATH}",
                    },
                    "folders": folder_checks,
                    "loaded": {
                        "cv_count": cv_scan["loaded_count"],
                        "spreadsheet_count": spreadsheet_scan["loaded_count"],
                        "spreadsheet_categories": {
                            name: len(items)
                            for name, items in spreadsheet_scan.get("categories", {}).items()
                        },
                    },
                    "next_actions": _next_actions(cv_scan["loaded_count"], spreadsheet_scan["loaded_count"]),
                },
                warnings=warnings,
            )

        return tool_handler("get_system_status", run)


def _folder_map() -> dict:
    return {
        "cv": str(settings.CV_UPLOAD_DIR),
        "excel": str(settings.EXCEL_UPLOAD_DIR),
        "survey": str(settings.SURVEY_UPLOAD_DIR),
        "legacy_uploads": str(settings.UPLOAD_DIR),
    }


def _folder_status(path: Path) -> dict:
    file_count = 0
    if path.exists():
        file_count = sum(1 for item in path.rglob("*") if item.is_file())
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "file_count": file_count,
    }


def _next_actions(cv_count: int, spreadsheet_count: int) -> list[str]:
    actions = ["Onyx'te refresh_file_library calistirip dosya kutuphanesini tazele."]
    if cv_count:
        actions.append("CV havuzu icin search_cvs veya analyze_cvs kullan.")
    if spreadsheet_count:
        actions.append("Anket icin auto_analyze_survey, Excel filtreleri icin auto_filter_excel_rows kullan.")
    return actions
