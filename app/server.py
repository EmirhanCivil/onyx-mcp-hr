"""Survey & Excel Intelligence MCP server."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from app.config import ensure_directories, settings
from app.logging_config import logger
from app.tools.agent_tools import register_agent_tools
from app.tools.chart_tools import register_chart_tools
from app.tools.cv_tools import register_cv_tools
from app.tools.document_tools import register_document_tools
from app.tools.excel_tools import register_excel_tools
from app.tools.hr_tools import register_hr_tools
from app.tools.hr_intelligence_tools import register_hr_intelligence_tools
from app.tools.library_tools import register_library_tools
from app.tools.report_tools import register_report_tools
from app.tools.semantic_compare_tools import register_semantic_compare_tools
from app.tools.survey_tools import register_survey_tools


def _auto_load_default_excel() -> None:
    """Prime the in-memory registry so Onyx can ask questions immediately."""

    try:
        from app.services.excel_service import excel_service

        if settings.AUTO_SCAN_UPLOADS_ENABLED:
            result = excel_service.scan_uploads()
            logger.info("Auto-scan uploads: %s dosya yuklendi.", result["loaded_count"])
            from app.services.cv_service import cv_service

            cv_result = cv_service.scan_cvs()
            logger.info("Auto-scan CVs: %s dosya yuklendi.", cv_result["loaded_count"])

        if settings.AUTO_LOAD_ENABLED and settings.AUTO_EXCEL_PATH:
            path = Path(settings.AUTO_EXCEL_PATH)
            if not path.exists():
                logger.warning("Auto-load dosyasi bulunamadi: %s", path)
                return
            result = excel_service.load_file(str(path))
            logger.info("Auto-load spreadsheet: %s -> %s", path.name, result["file"]["file_id"])
    except Exception as exc:
        logger.error("Auto-load hatasi: %s", exc)


def create_server() -> FastMCP:
    """Create and configure the MCP server."""

    ensure_directories()
    mcp = FastMCP("Survey & Excel Intelligence MCP")

    register_agent_tools(mcp)
    register_excel_tools(mcp)
    register_cv_tools(mcp)
    register_document_tools(mcp)
    register_library_tools(mcp)
    register_hr_tools(mcp)
    register_hr_intelligence_tools(mcp)
    register_survey_tools(mcp)
    register_chart_tools(mcp)
    register_report_tools(mcp)
    register_semantic_compare_tools(mcp)

    _auto_load_default_excel()
    logger.info("Survey & Excel Intelligence MCP tools registered.")
    return mcp


mcp = create_server()


if __name__ == "__main__":
    logger.info("Server baslatiliyor: http://%s:%s%s", settings.MCP_HOST, settings.MCP_PORT, settings.MCP_PATH)
    mcp.run(
        transport=settings.MCP_TRANSPORT,
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        path=settings.MCP_PATH,
    )
