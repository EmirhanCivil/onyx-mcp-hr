"""MCP tools for CV folder discovery and search."""

from __future__ import annotations

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.cv_service import cv_service


def register_cv_tools(mcp: FastMCP) -> None:
    """Register CV discovery tools."""

    @mcp.tool()
    def scan_cvs() -> str:
        """data/uploads/cv klasorundeki TXT/DOCX CV dosyalarini tarar."""

        return tool_handler(
            "scan_cvs",
            lambda: ok_response("scan_cvs", "CV klasoru tarandi.", cv_service.scan_cvs()),
        )

    @mcp.tool()
    def list_cvs() -> str:
        """Yuklu CV dosyalarini listeler."""

        def run():
            cv_service.scan_cvs()
            return ok_response("list_cvs", "CV dosyalari listelendi.", {"cvs": cv_service.list_cvs()})

        return tool_handler("list_cvs", run)

    @mcp.tool()
    def audit_cv_library() -> str:
        """CV metinlerinin okunabilirligini ve eksik alanlarini kontrol eder."""

        def run():
            return ok_response("audit_cv_library", "CV kutuphanesi denetlendi.", cv_service.audit_library())

        return tool_handler("audit_cv_library", run)

    @mcp.tool()
    def summarize_cv_library() -> str:
        """CV havuzunu yetkinlik, pozisyon, sehir, egitim ve durum bazinda ozetler."""

        def run():
            cv_service.scan_cvs()
            return ok_response("summarize_cv_library", "CV havuzu ozetlendi.", cv_service.summarize_library())

        return tool_handler("summarize_cv_library", run)

    @mcp.tool()
    def get_cv_detail(cv_id: str = "", query: str = "", include_full_text: bool = False) -> str:
        """Tek CV icin isim, pozisyon, iletisim, egitim, yetkinlik, deneyim ve proje detaylarini getirir."""

        def run():
            cv_service.scan_cvs()
            return ok_response("get_cv_detail", "CV detayi getirildi.", cv_service.get_cv_detail(cv_id, query, include_full_text))

        return tool_handler("get_cv_detail", run)

    @mcp.tool()
    def search_cvs(query: str, limit: int = 10) -> str:
        """CV metinlerinde anahtar kelime arar ve kisa eslesme parcalari dondurur."""

        def run():
            cv_service.scan_cvs()
            return ok_response("search_cvs", "CV aramasi tamamlandi.", cv_service.search_cvs(query, limit))

        return tool_handler("search_cvs", run)

    @mcp.tool()
    def analyze_cvs(query: str = "", limit: int = 10) -> str:
        """CV havuzunda yetkinlik/aday sorgusu icin sirali kisa liste uretir."""

        def run():
            cv_service.scan_cvs()
            return ok_response("analyze_cvs", "CV analizi tamamlandi.", cv_service.analyze_cvs(query, limit))

        return tool_handler("analyze_cvs", run)
