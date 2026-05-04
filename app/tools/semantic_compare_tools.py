"""MCP tools for semantic field comparison between two spreadsheets."""

from __future__ import annotations

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.semantic_compare_service import semantic_compare_service


def register_semantic_compare_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def semantic_compare_excel_field(
        file_id_a: str,
        file_id_b: str,
        user_question: str,
        key_hint: str = "",
        field_hint: str = "",
        limit: int = 50,
        export: bool = True,
    ) -> str:
        """Kullanici belirli bir alan/kavram soruyorsa SADECE o alanin farkini karsilastirir.

        - Tum Excel'i karsilastirmaz.
        - Anahtar kolon (key) otomatik tespit edilir, gerekirse key_hint ile netlestirilir.
        - Hedef kolon otomatik tespit edilir, gerekirse field_hint ile netlestirilir.
        - Buyuk sonuc varsa preview + export uretir.
        """

        def run():
            result = semantic_compare_service.semantic_compare_excel_field(
                file_id_a=file_id_a,
                file_id_b=file_id_b,
                user_question=user_question,
                key_hint=key_hint or None,
                field_hint=field_hint or None,
                export=export,
                limit=limit,
            )
            status = result.get("status", "success")
            message = result.get("message", "Semantic comparison tamamlandi.")
            data = result.get("data", {})
            warnings = result.get("warnings", [])
            generated_outputs = result.get("generated_outputs", [])
            if status != "success":
                return ok_response("semantic_compare_excel_field", message, data, warnings=warnings, generated_outputs=generated_outputs)
            return ok_response("semantic_compare_excel_field", "Semantic alan karsilastirmasi tamamlandi.", data, warnings=warnings, generated_outputs=generated_outputs)

        return tool_handler("semantic_compare_excel_field", run)
