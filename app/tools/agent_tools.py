"""High-level agent-facing tools that choose the right lower-level workflow."""

from __future__ import annotations

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.chart_service import chart_service
from app.services.cv_service import cv_service
from app.services.excel_compare_service import excel_compare_service
from app.services.excel_service import excel_service
from app.services.hr_service import hr_service
from app.services.report_service import report_service
from app.services.semantic_compare_service import semantic_compare_service
from app.services.survey_analysis_service import survey_analysis_service
from app.services.workbook_structure_service import workbook_structure_service
from app.utils.dataframe_utils import normalize_column_name


def register_agent_tools(mcp: FastMCP) -> None:
    """Register one-call tools designed for Onyx agent routing."""

    @mcp.tool()
    def answer_cv_question(question: str, limit: int = 5) -> str:
        """CV sorulari icin arama, detay ve cevap baglamini tek seferde hazirlar."""

        def run():
            return ok_response("answer_cv_question", "CV soru baglami hazirlandi.", cv_service.answer_question(question, limit))

        return tool_handler("answer_cv_question", run)

    @mcp.tool()
    def answer_excel_question(question: str, file_query: str = "", limit: int = 20, export: bool = False) -> str:
        """Genel Excel/CSV sorulari icin dosya secimi, kalite kontrol, filtre veya kiyaslama baglami hazirlar."""

        def run():
            excel_service.scan_uploads()
            normalized = normalize_column_name(question)
            selected = excel_service.select_file(file_query or question, "spreadsheet")
            if not selected:
                return ok_response(
                    "answer_excel_question",
                    "Uygun tablo dosyasi bulunamadi.",
                    {"question": question, "file_query": file_query},
                    warnings=["Once dosyayi uploads/excel veya uploads/survey altina koyup refresh_file_library calistirin."],
                )

            data = {
                "question": question,
                "selected_file": selected,
                "quality_audit": excel_service.audit_quality(selected["file_id"]),
                "answer_guidance": "Ham satirlari komple basma; audit, preview ve tool sonucuna dayanarak kisa cevap ver.",
            }
            try:
                # If this is a multi-sheet workbook, provide structure context so the agent can pick
                # the correct sheet(s) without relying on sheet names.
                workbook = workbook_structure_service.analyze(selected["file_id"], task_hint=question)
                data["workbook_structure"] = workbook
            except Exception:
                pass
            files = []
            if any(token in normalized for token in (
                "karsilastir", "kiyas", "fark", "degis", "eski", "yeni",
                "ayni", "tutuyor", "compare", "diff", "difference", "same", "changed",
            )):
                matches = excel_service.find_files("", "spreadsheet")["matches"]
                second = next((item for item in matches if item["file_id"] != selected["file_id"]), None)
                if second:
                    # If the user asks about a specific field/concept (price/status/active etc.),
                    # use semantic field comparison; only run full auto_compare when explicitly requested.
                    full_tokens = ("tum", "tumu", "tümü", "butun", "bütün", "her sey", "herşey", "all columns", "entire file", "full compare")
                    full_compare_requested = any(tok in normalized for tok in full_tokens)

                    field_tokens = ("fiyat", "price", "stok", "stock", "aktif", "pasif", "active", "inactive", "iletildi", "iletilmedi", "sent", "delivered", "telefon", "phone", "durum", "status", "stage")
                    field_diff_hint = any(tok in normalized for tok in field_tokens)

                    if field_diff_hint and not full_compare_requested:
                        semantic = semantic_compare_service.semantic_compare_excel_field(
                            file_id_a=selected["file_id"],
                            file_id_b=second["file_id"],
                            user_question=question,
                            export=export,
                            limit=min(limit, 50),
                        )
                        data["mode"] = "semantic_field_compare"
                        data["comparison"] = semantic.get("data", {})
                        files = [item.get("path") for item in (semantic.get("generated_outputs") or []) if isinstance(item, dict) and item.get("path")]  # type: ignore[assignment]
                    else:
                        compare = excel_compare_service.compare_auto(selected["file_id"], second["file_id"], key_query=question, limit=limit, export=export)
                        files = compare.pop("files", [])
                        data["mode"] = "compare"
                        data["comparison"] = compare
                else:
                    data["mode"] = "audit"
                    data["warning"] = "Kiyaslama icin ikinci dosya bulunamadi."
            elif any(token in normalized for token in ("filtre", "listele", "olanlar", "olmayan", "durumu", "status", "sehir", "pozisyon")):
                filtered = excel_compare_service.filter_rows(selected["file_id"], query=question, limit=limit, export=export)
                files = filtered.pop("files", [])
                data["mode"] = "filter"
                data["filter_result"] = filtered
            else:
                data["mode"] = "profile"
                data["profile"] = excel_service.profile(selected["file_id"], preview_rows=min(limit, 20))

            return ok_response("answer_excel_question", "Excel soru baglami hazirlandi.", data, files=files)

        return tool_handler("answer_excel_question", run)

    @mcp.tool()
    def answer_survey_question(question: str, file_query: str = "", include_action_plan: bool = True, include_outputs: bool = True) -> str:
        """Anket sorulari icin dosya secimi, overview, yorum ve aksiyon baglami hazirlar."""

        def run():
            excel_service.scan_uploads()
            selected = excel_service.select_file(file_query or question, "survey")
            if not selected:
                return ok_response(
                    "answer_survey_question",
                    "Uygun anket dosyasi bulunamadi.",
                    {"question": question, "file_query": file_query},
                    warnings=["Anket dosyasini uploads/survey altina koyun veya dosya adini belirtin."],
                )
            overview = survey_analysis_service.overview(selected["file_id"])
            data = {
                "question": question,
                "selected_file": selected,
                "overview": overview,
                "answer_guidance": "Skor, grup, yorum ve generated_outputs alanlarini kullanarak yonetici dostu cevap ver; ham JSON basma.",
            }
            recommended = overview.get("recommended_group_analysis")
            if recommended:
                data["group_analysis"] = survey_analysis_service.by_group(
                    selected["file_id"],
                    recommended["group_col"],
                    ",".join(recommended["score_columns"]),
                )
            comment_columns = overview.get("recommended_comment_columns", [])
            if comment_columns:
                data["comment_analysis"] = survey_analysis_service.comments(selected["file_id"], ",".join(comment_columns))
            data["manager_pack"] = survey_analysis_service.executive_summary(
                selected["file_id"],
                include_comments=bool(comment_columns),
            )
            files = []
            charts = []
            outputs = []
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
            if include_action_plan or any(token in normalize_column_name(question) for token in ("aksiyon", "oneri", "plan", "ne yapmali")):
                action = hr_service.survey_action_plan(file_query, export=False)
                data["action_plan"] = action.get("action_plan", {})
            return ok_response(
                "answer_survey_question",
                "Anket soru bağlamı hazırlandı.",
                data,
                files=list(dict.fromkeys(files)),
                charts=list(dict.fromkeys(charts)),
                generated_outputs=outputs,
                warnings=list(dict.fromkeys(warnings)),
            )

        return tool_handler("answer_survey_question", run)
