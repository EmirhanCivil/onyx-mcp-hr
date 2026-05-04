"""Premium HR workflow tools and prompt templates."""

from __future__ import annotations

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.candidate_pool_service import candidate_pool_service
from app.services.excel_cv_match_service import excel_cv_match_service
from app.services.hr_service import hr_service


def register_hr_tools(mcp: FastMCP) -> None:
    """Register HR decision-support workflows."""

    @mcp.tool()
    def analyze_candidate_pool(file_query: str = "", file_id: str = "", limit: int = 20, export: bool = False) -> str:
        """Aday havuzu raporu: dagilimlar, eksik veri, duplicate ve opsiyonel export paketleri."""

        def run():
            result = candidate_pool_service.analyze(file_query=file_query, file_id=file_id, limit=limit, export=export)
            data = result.get("data", {})
            files = result.get("files", [])
            outputs = result.get("generated_outputs", [])
            return ok_response(
                "analyze_candidate_pool",
                "Aday havuzu analizi tamamlandi.",
                data,
                files=files,
                generated_outputs=outputs,
            )

        return tool_handler("analyze_candidate_pool", run)

    @mcp.tool()
    def match_excel_candidates_to_cvs(file_query: str = "", file_id: str = "", limit: int = 25, export: bool = True) -> str:
        """Excel aday kayitlarini CV dosyalariyla eslestirir; eslesen/eslesmeyenleri raporlar ve export eder."""

        def run():
            result = excel_cv_match_service.match(file_query=file_query, file_id=file_id, limit=limit, export=export)
            data = result.get("data", {})
            files = result.get("files", [])
            outputs = result.get("generated_outputs", [])
            return ok_response(
                "match_excel_candidates_to_cvs",
                "Excel–CV eslestirme tamamlandi.",
                data,
                files=files,
                generated_outputs=outputs,
            )

        return tool_handler("match_excel_candidates_to_cvs", run)

    @mcp.tool()
    def create_candidate_shortlist(
        role: str,
        required_skills: str = "",
        preferred_skills: str = "",
        query: str = "",
        limit: int = 10,
        anonymize: bool = False,
        include_snippets: bool = False,
    ) -> str:
        """CV havuzundan role gore aday kisa listesi uretir; otomatik karar vermez."""

        def run():
            return ok_response(
                "create_candidate_shortlist",
                "Aday kisa listesi hazirlandi.",
                hr_service.candidate_shortlist(role, required_skills, preferred_skills, query, limit, anonymize, include_snippets),
            )

        return tool_handler("create_candidate_shortlist", run)

    @mcp.tool()
    def analyze_recruiting_pipeline(
        file_query: str = "",
        stage_column: str = "",
        position_column: str = "",
        group_column: str = "",
        source_column: str = "",
        limit: int = 10,
    ) -> str:
        """Aday Excel'inden funnel, kaynak karmasi, darbogaz ve veri kalitesi ozeti cikarir."""

        def run():
            return ok_response(
                "analyze_recruiting_pipeline",
                "Aday pipeline analizi tamamlandi.",
                hr_service.recruiting_pipeline(file_query, stage_column, position_column, group_column, source_column, limit),
            )

        return tool_handler("analyze_recruiting_pipeline", run)

    @mcp.tool()
    def create_survey_action_plan(
        file_query: str = "",
        group_col: str = "",
        score_columns: str = "",
        comment_columns: str = "",
        min_group_size: int = 5,
        export: bool = True,
    ) -> str:
        """Anket sonuclarindan HRBP aksiyon plani, sahiplik ve takip metrikleri uretir."""

        def run():
            data = hr_service.survey_action_plan(file_query, group_col, score_columns, comment_columns, min_group_size, export)
            files = data.get("files", [])
            return ok_response("create_survey_action_plan", "Anket aksiyon plani hazirlandi.", data, files=files)

        return tool_handler("create_survey_action_plan", run)

    @mcp.prompt()
    def hr_health_check_prompt() -> str:
        """Onyx icin baslangic kontrol akisi."""

        return (
            "Once get_system_status calistir. Ardindan list_file_library ile dosya kutuphanesini ozetle. "
            "Eksik klasor, bos CV havuzu veya bos anket/Excel klasoru varsa net aksiyon oner. "
            "Cevapta MCP URL, yuklenen CV sayisi, yuklenen Excel/anket sayisi ve siradaki en iyi 3 tool'u belirt."
        )

    @mcp.prompt()
    def candidate_shortlist_prompt(role: str, required_skills: str = "", preferred_skills: str = "") -> str:
        """Aday kisa listeleme icin standart prompt."""

        return (
            f"{role} rolu icin create_candidate_shortlist calistir. "
            f"Zorunlu yetkinlikler: {required_skills}. Tercihli yetkinlikler: {preferred_skills}. "
            "Cevapta sadece karar destegi verdigini, nihai karar olmadigini belirt; eksik yetkinlikleri ve onerilen sonraki adimi tablo gibi ozetle."
        )

    @mcp.prompt()
    def survey_action_plan_prompt() -> str:
        """Anket aksiyon planlama icin standart prompt."""

        return (
            "create_survey_action_plan calistir. Sonra en dusuk grup/skor basliklarini, yorum temalarini, "
            "0-30 ve 30-60 gun aksiyonlarini ve calisanlara iletisim notunu kisa bir yonetici ozeti olarak yaz."
        )
