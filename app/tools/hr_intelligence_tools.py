"""Corporate HR intelligence tools (selection, normalization, dashboard, funnels, segments, root-cause)."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.core.file_registry import file_registry
from app.services.excel_query_service import excel_query_service
from app.services.excel_service import excel_service
from app.services.hr_column_normalization_service import hr_column_normalization_service
from app.services.hr_dashboard_service import hr_dashboard_service
from app.services.hr_file_selection_service import hr_file_selection_service
from app.services.hr_funnel_service import hr_funnel_service
from app.services.hr_quality_service import hr_quality_service
from app.services.hr_segment_compare_service import hr_segment_compare_service
from app.services.hr_transitions_service import hr_transitions_service
from app.services.hr_question_suggestion_service import hr_question_suggestion_service
from app.services.survey_root_cause_service import survey_root_cause_service


def register_hr_intelligence_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def auto_select_hr_file(query: str = "", preferred: str = "") -> str:
        """Kullanici dosya adi vermese bile uygun CV / aday Excel'i / anket dosyasini otomatik secer; alternatifleri dondurur."""

        def run():
            data = hr_file_selection_service.auto_select(query=query, preferred=preferred)
            return ok_response("auto_select_hr_file", "Dosya secimi tamamlandi.", data, warnings=data.get("warnings", []))

        return tool_handler("auto_select_hr_file", run)

    @mcp.tool()
    def normalize_hr_columns(file_id: str, include_all_candidates: bool = False) -> str:
        """HR kolon normalizasyonu: TR/EN kolon adlarini canonical alanlara eslestirir; status normalize ipuclari verir."""

        def run():
            df = file_registry.get_frame(file_id)
            data = hr_column_normalization_service.normalize(df, include_all_candidates=include_all_candidates)
            return ok_response("normalize_hr_columns", "Kolon normalizasyonu tamamlandi.", data, warnings=data.get("warnings", []))

        return tool_handler("normalize_hr_columns", run)

    @mcp.tool()
    def calculate_hr_data_quality_score(file_query: str = "", file_id: str = "", include_cv_match: bool = True) -> str:
        """Aday Excel'i icin 0-100 veri kalite skoru + problem ve aksiyon onerileri."""

        def run():
            data = hr_quality_service.score(file_query=file_query, file_id=file_id, include_cv_match=include_cv_match)
            return ok_response("calculate_hr_data_quality_score", "Veri kalite skoru hesaplandi.", data)

        return tool_handler("calculate_hr_data_quality_score", run)

    @mcp.tool()
    def explain_hr_query_plan(
        file_query: str = "",
        file_id: str = "",
        natural_query: str = "",
        structured_query_json: str = "",
        logic: str = "",
        return_mode: str = "sample",
        sample_limit: int = 10,
        export: bool = False,
    ) -> str:
        """Dogal dil sorguyu hangi filtre planina cevirdigini aciklar (kolon eslesmeleri + varsayimlar + count/preview/export)."""

        def run():
            excel_service.scan_uploads()
            target = file_id
            selected = None
            if not target:
                selected = excel_service.select_file(file_query or natural_query, "spreadsheet")
                target = selected["file_id"] if selected else ""
            if not target:
                return ok_response(
                    "explain_hr_query_plan",
                    "Uygun tablo dosyasi bulunamadi.",
                    {"file_query": file_query, "natural_query": natural_query},
                    warnings=["Dosyayi uploads altina ekleyip refresh_file_library calistirin."],
                )
            structured = None
            if structured_query_json:
                try:
                    parsed = json.loads(structured_query_json)
                    structured = parsed if isinstance(parsed, dict) else None
                except Exception:
                    structured = None

            result = excel_query_service.query_rows(
                file_id=target,
                structured_query=structured,
                natural_query=natural_query,
                return_mode=return_mode,
                sample_limit=sample_limit,
                export=export,
            )
            plan = {
                "selected_file": selected or file_registry.get_meta(target).__dict__,
                "input": {
                    "natural_query": natural_query,
                    "structured_query_json": structured_query_json,
                    "return_mode": return_mode,
                    "sample_limit": sample_limit,
                    "export": export,
                },
                "resolved_fields": result.get("data", {}).get("resolved_fields"),
                "conditions_applied": result.get("data", {}).get("conditions_applied"),
                "logic": result.get("data", {}).get("logic"),
                "warnings": result.get("warnings", []),
                "matched_count": result.get("data", {}).get("matched_count"),
                "returned_rows_count": result.get("data", {}).get("returned_rows_count"),
                "export_path": result.get("data", {}).get("export_path"),
            }
            data = {"plan": plan, "result": result.get("data", {})}
            return ok_response(
                "explain_hr_query_plan",
                "Sorgu plani olusturuldu.",
                data,
                warnings=list(dict.fromkeys((result.get("warnings", []) or []) + (plan.get("warnings", []) or []))),
                generated_outputs=result.get("generated_outputs", []),
            )

        return tool_handler("explain_hr_query_plan", run)

    @mcp.tool()
    def generate_hr_overview_dashboard(file_query: str = "", file_id: str = "", include_quality: bool = True) -> str:
        """Tek komutla aday havuzu dashboard ozetini cikarir (durum, top segmentler, eksik/duplicate, kalite skoru)."""

        def run():
            data = hr_dashboard_service.overview(file_query=file_query, file_id=file_id, include_quality=include_quality)
            return ok_response("generate_hr_overview_dashboard", "HR dashboard ozeti hazirlandi.", data)

        return tool_handler("generate_hr_overview_dashboard", run)

    @mcp.tool()
    def analyze_candidate_stage_transitions(
        file_query_a: str = "",
        file_query_b: str = "",
        file_id_a: str = "",
        file_id_b: str = "",
        key_query: str = "email telefon candidate id aday id",
        export: bool = True,
        limit: int = 50,
    ) -> str:
        """Iki donem Excel arasinda adaylarin asama gecislerini analiz eder; yeni/dusen/degisenleri ve transition tablosunu export eder."""

        def run():
            result = hr_transitions_service.analyze(
                file_query_a=file_query_a,
                file_query_b=file_query_b,
                file_id_a=file_id_a,
                file_id_b=file_id_b,
                key_query=key_query,
                export=export,
                limit=limit,
            )
            return ok_response(
                "analyze_candidate_stage_transitions",
                "Surec gecis analizi tamamlandi.",
                result.get("data", {}),
                files=result.get("files", []),
                generated_outputs=result.get("generated_outputs", []),
            )

        return tool_handler("analyze_candidate_stage_transitions", run)

    @mcp.tool()
    def analyze_position_funnel(
        file_query: str = "",
        file_id: str = "",
        position_col: str = "",
        status_col: str = "",
        top_n: int = 15,
        export: bool = False,
    ) -> str:
        """Pozisyon bazli funnel analizi (donusum oranlari + darboğaz sinyalleri)."""

        def run():
            result = hr_funnel_service.analyze_position_funnel(
                file_query=file_query,
                file_id=file_id,
                position_col=position_col,
                status_col=status_col,
                top_n=top_n,
                export=export,
            )
            return ok_response(
                "analyze_position_funnel",
                "Pozisyon funnel analizi tamamlandi.",
                result.get("data", {}),
                files=result.get("files", []),
                generated_outputs=result.get("generated_outputs", []),
            )

        return tool_handler("analyze_position_funnel", run)

    @mcp.tool()
    def compare_candidate_segments(
        file_query: str = "",
        file_id: str = "",
        segment_field: str = "university",
        top_n: int = 20,
        export: bool = False,
    ) -> str:
        """Segment karsilastirma: okul/sehir/bolum/pozisyon/departman/kaynak gibi segmentlerde teknik/hr/olumlu oranlarini ozetler."""

        def run():
            result = hr_segment_compare_service.compare(
                file_query=file_query,
                file_id=file_id,
                segment_field=segment_field,
                top_n=top_n,
                export=export,
            )
            return ok_response(
                "compare_candidate_segments",
                "Segment karsilastirma tamamlandi.",
                result.get("data", {}),
                files=result.get("files", []),
                generated_outputs=result.get("generated_outputs", []),
            )

        return tool_handler("compare_candidate_segments", run)

    @mcp.tool()
    def analyze_survey_root_causes(file_id: str, min_group_size: int = 5, low_score_threshold: float = 0.0, limit: int = 10) -> str:
        """Dusuk skor boyutlari icin tema+departman birlikte root cause analizi ve aksiyon onerileri."""

        def run():
            threshold = None if low_score_threshold <= 0 else float(low_score_threshold)
            data = survey_root_cause_service.analyze(file_id=file_id, min_group_size=min_group_size, low_score_threshold=threshold, limit=limit)
            return ok_response("analyze_survey_root_causes", "Kok neden analizi tamamlandi.", data)

        return tool_handler("analyze_survey_root_causes", run)

    @mcp.tool()
    def suggest_hr_questions() -> str:
        """Yuklenen dosya tipine gore kullanicinin sorabilecegi ornek sorulari onerir."""

        def run():
            data = hr_question_suggestion_service.suggest()
            return ok_response("suggest_hr_questions", "Soru onerileri hazirlandi.", data)

        return tool_handler("suggest_hr_questions", run)

