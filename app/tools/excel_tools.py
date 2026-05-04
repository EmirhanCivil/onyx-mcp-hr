"""MCP tools for Excel/CSV intelligence."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from app.core.response_schema import ok_response, tool_handler
from app.services.excel_compare_service import excel_compare_service
from app.services.excel_query_service import excel_query_service
from app.services.excel_service import excel_service
from app.services.workbook_structure_service import workbook_structure_service


def register_excel_tools(mcp: FastMCP) -> None:
    """Register Excel loading, profiling, comparison, filtering, and duplicate tools."""

    @mcp.tool()
    def load_spreadsheet(file_path: str, sheet_name: str = "0", delimiter: str = "") -> str:
        """Excel/CSV dosyasini Python tarafinda yukler ve file_id dondurur."""

        def run():
            sheet: str | int | None = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
            data = excel_service.load_file(file_path, sheet, delimiter or None)
            return ok_response("load_spreadsheet", "Dosya basariyla yuklendi.", data)

        return tool_handler("load_spreadsheet", run)

    @mcp.tool()
    def scan_uploads() -> str:
        """Excel ve anket klasorlerini tarar, yukler ve kategorilere ayirir."""

        return tool_handler(
            "scan_uploads",
            lambda: ok_response("scan_uploads", "Uploads klasoru tarandi ve dosyalar yuklendi.", excel_service.scan_uploads()),
        )

    @mcp.tool()
    def list_loaded_spreadsheets() -> str:
        """Yuklu spreadsheet dosyalarini listeler; cagri oncesi klasorleri tazeler."""

        def run():
            excel_service.scan_uploads()
            return ok_response(
                "list_loaded_spreadsheets",
                "Yuklu dosyalar listelendi.",
                {"files": excel_service.list_loaded_files(), "categories": excel_service.group_loaded_files()},
            )

        return tool_handler("list_loaded_spreadsheets", run)

    @mcp.tool()
    def list_available_files(category: str = "") -> str:
        """Yuklu dosyalari survey/excel/csv/cv kategorilerine gore listeler."""

        def run():
            excel_service.scan_uploads()
            grouped = excel_service.group_loaded_files()
            if category:
                return ok_response(
                    "list_available_files",
                    "Kategoriye gore dosyalar listelendi.",
                    {"category": category, "files": grouped.get(category, [])},
                )
            return ok_response("list_available_files", "Kategorilere gore dosyalar listelendi.", {"categories": grouped})

        return tool_handler("list_available_files", run)

    @mcp.tool()
    def find_spreadsheet(query: str = "", category: str = "") -> str:
        """Dosya adi, kolon adi veya kategoriye gore yuklu spreadsheet arar."""

        def run():
            excel_service.scan_uploads()
            return ok_response("find_spreadsheet", "Eslesen dosyalar listelendi.", excel_service.find_files(query, category))

        return tool_handler("find_spreadsheet", run)

    @mcp.tool()
    def profile_spreadsheet(file_id: str, preview_rows: int = 10) -> str:
        """Yuklu dosyanin kolon, tip, eksik veri ve guvenli onizleme ozetini dondurur."""

        return tool_handler(
            "profile_spreadsheet",
            lambda: ok_response("profile_spreadsheet", "Dosya profili cikarildi.", excel_service.profile(file_id, preview_rows)),
        )

    @mcp.tool()
    def inspect_workbook_sheets(file_path: str = "", file_query: str = "") -> str:
        """Excel workbook icindeki sheetleri listeler ve en uygun sheet onerir."""

        def run():
            target_path = file_path
            selected = None
            if not target_path:
                excel_service.scan_uploads()
                selected = excel_service.select_file(file_query, "spreadsheet")
                target_path = selected["path"] if selected else ""
            if not target_path:
                return ok_response(
                    "inspect_workbook_sheets",
                    "Workbook bulunamadi.",
                    {"file_query": file_query},
                    warnings=["Excel dosyasini data/uploads/excel veya data/uploads/survey altina ekleyin."],
                )
            data = excel_service.inspect_workbook(target_path)
            if selected:
                data["selected_file"] = selected
            return ok_response("inspect_workbook_sheets", "Workbook sheet envanteri hazirlandi.", data)

        return tool_handler("inspect_workbook_sheets", run)

    @mcp.tool()
    def analyze_workbook_structure(file_id: str, task_hint: str = "") -> str:
        """Workbook icindeki tum sheet'leri profiller, veri sheet'lerini secer ve strateji onerir."""

        def run():
            data = workbook_structure_service.analyze(file_id=file_id, task_hint=task_hint)
            return ok_response("analyze_workbook_structure", "Workbook sheet analizi tamamlandi.", data, warnings=data.get("warnings", []))

        return tool_handler("analyze_workbook_structure", run)

    @mcp.tool()
    def audit_spreadsheet_quality(file_id: str = "", file_query: str = "", category: str = "") -> str:
        """Her tip Excel/CSV icin eksik veri, duplicate, format/kalite problemleri ve onerilen tool taramasi yapar."""

        def run():
            excel_service.scan_uploads()
            target = file_id
            selected = None
            if not target:
                selected = excel_service.select_file(file_query, category or "spreadsheet")
                target = selected["file_id"] if selected else ""
            if not target:
                return ok_response(
                    "audit_spreadsheet_quality",
                    "Denetlenecek dosya bulunamadi.",
                    {"file_query": file_query, "category": category},
                    warnings=["Once list_file_library veya find_spreadsheet ile uygun dosyayi bulun."],
                )
            data = excel_service.audit_quality(target)
            if selected:
                data["selected_file"] = selected
            return ok_response("audit_spreadsheet_quality", "Veri kalite denetimi tamamlandi.", data, warnings=data.get("warnings", []))

        return tool_handler("audit_spreadsheet_quality", run)

    @mcp.tool()
    def compare_spreadsheet_columns(file_id_a: str, file_id_b: str) -> str:
        """Iki Excel/CSV dosyasinin sutun semasini karsilastirir."""

        return tool_handler(
            "compare_spreadsheet_columns",
            lambda: ok_response("compare_spreadsheet_columns", "Sutun farklari cikarildi.", excel_compare_service.compare_schema(file_id_a, file_id_b)),
        )

    @mcp.tool()
    def compare_spreadsheet_rows(
        file_id_a: str,
        file_id_b: str,
        compare_columns: str = "",
        limit: int = 50,
        export: bool = False,
    ) -> str:
        """Iki dosya arasinda farkli satirlari bulur."""

        def run():
            data = excel_compare_service.compare_rows(file_id_a, file_id_b, compare_columns, limit, export)
            files = data.pop("exported_files", [])
            return ok_response("compare_spreadsheet_rows", "Satir farklari cikarildi.", data, files=files)

        return tool_handler("compare_spreadsheet_rows", run)

    @mcp.tool()
    def compare_spreadsheet_by_key(
        file_id_a: str,
        file_id_b: str,
        key_columns: str,
        compare_columns: str = "",
        limit: int = 50,
    ) -> str:
        """Iki dosyayi anahtar kolonlara gore eslestirir ve degisen kayitlari dondurur."""

        return tool_handler(
            "compare_spreadsheet_by_key",
            lambda: ok_response(
                "compare_spreadsheet_by_key",
                "Anahtar bazli karsilastirma tamamlandi.",
                excel_compare_service.compare_by_key(file_id_a, file_id_b, key_columns, compare_columns, limit),
            ),
        )

    @mcp.tool()
    def auto_compare_spreadsheets(
        file_query_a: str = "",
        file_query_b: str = "",
        key_query: str = "",
        compare_columns: str = "",
        category: str = "spreadsheet",
        limit: int = 50,
        export: bool = False,
    ) -> str:
        """Iki dosyayi file_id/kolon adi bilmeden otomatik kolon eslestirme ile karsilastirir."""

        def run():
            excel_service.scan_uploads()
            matches = excel_service.find_files("", category)["matches"]
            first = excel_service.select_file(file_query_a, category)
            second = excel_service.select_file(file_query_b, category) if file_query_b else None
            if not second and len(matches) >= 2:
                second = next((item for item in matches if not first or item["file_id"] != first["file_id"]), None)
            if not first or not second:
                return ok_response(
                    "auto_compare_spreadsheets",
                    "Karsilastirma icin iki uygun dosya bulunamadi.",
                    {"available_files": matches, "file_query_a": file_query_a, "file_query_b": file_query_b},
                    warnings=["Iki farkli Excel/CSV dosyasini uploads altina ekleyin veya file_query ile secimi netlestirin."],
                )
            data = excel_compare_service.compare_auto(first["file_id"], second["file_id"], key_query, compare_columns, limit, export)
            files = data.pop("files", [])
            return ok_response("auto_compare_spreadsheets", "Otomatik dosya karsilastirmasi tamamlandi.", data, files=files)

        return tool_handler("auto_compare_spreadsheets", run)

    @mcp.tool()
    def filter_spreadsheet_rows(
        file_id: str,
        column: str = "",
        value: str = "",
        mode: str = "equals",
        query: str = "",
        limit: int = 50,
        export: bool = False,
    ) -> str:
        """Kolon/deger veya dogal sorguya gore satirlari filtreler."""

        def run():
            data = excel_compare_service.filter_rows(file_id, column, value, mode, query, limit, export)
            files = data.pop("files", [])
            return ok_response("filter_spreadsheet_rows", "Satir filtresi tamamlandi.", data, files=files)

        return tool_handler("filter_spreadsheet_rows", run)

    @mcp.tool()
    def query_spreadsheet_rows(
        file_id: str,
        natural_query: str = "",
        structured_query_json: dict[str, Any] | str | None = None,
        return_mode: str = "sample",
        sample_limit: int = 10,
        export: bool = False,
    ) -> str:
        """Full-scan satir sorgusu: kesin matched_count + limitli ornek / export / summary."""

        def run():
            structured_query = None
            if structured_query_json is not None and structured_query_json != "":
                # Some clients may pass an object; accept both stringified JSON and dict-like values.
                parsed = structured_query_json
                if isinstance(structured_query_json, str):
                    try:
                        parsed = json.loads(structured_query_json)
                    except Exception as exc:
                        return ok_response(
                            "query_spreadsheet_rows",
                            "Structured query JSON parse edilemedi.",
                            {"structured_query_json": structured_query_json},
                            warnings=[str(exc)],
                        )
                if not isinstance(parsed, dict):
                    return ok_response(
                        "query_spreadsheet_rows",
                        "Structured query dict olmali (JSON object).",
                        {"structured_query_json": structured_query_json},
                        warnings=["structured_query_json JSON object/dict formatinda olmali."],
                    )
                structured_query = parsed

            result = excel_query_service.query_rows(
                file_id=file_id,
                structured_query=structured_query,
                natural_query=natural_query,
                return_mode=return_mode,
                sample_limit=sample_limit,
                export=export,
            )

            data = result.get("data", {})
            warnings = result.get("warnings", [])
            generated_outputs = result.get("generated_outputs", [])
            return ok_response(
                "query_spreadsheet_rows",
                "Sorgu basariyla tamamlandi.",
                data,
                warnings=warnings,
                generated_outputs=generated_outputs,
            )

        return tool_handler("query_spreadsheet_rows", run)

    @mcp.tool()
    def auto_query_spreadsheet_rows(
        query: str,
        file_query: str = "",
        category: str = "spreadsheet",
        structured_query_json: dict[str, Any] | str | None = None,
        return_mode: str = "sample",
        sample_limit: int = 10,
        export: bool = False,
    ) -> str:
        """File_id istemeden uygun tabloyu bulur ve query_spreadsheet_rows (full scan) calistirir."""

        def run():
            excel_service.scan_uploads()
            selected = excel_service.select_file(file_query or query, category)
            if not selected:
                return ok_response(
                    "auto_query_spreadsheet_rows",
                    "Uygun tablo dosyasi bulunamadi.",
                    {"query": query, "file_query": file_query, "category": category},
                    warnings=["Dosyayi uploads/excel veya uploads/survey altina ekleyip refresh_file_library calistirin."],
                )
            structured_query = None
            if structured_query_json is not None and structured_query_json != "":
                parsed = structured_query_json
                if isinstance(structured_query_json, str):
                    try:
                        parsed = json.loads(structured_query_json)
                    except Exception as exc:
                        return ok_response(
                            "auto_query_spreadsheet_rows",
                            "Structured query JSON parse edilemedi.",
                            {"structured_query_json": structured_query_json, "selected_file": selected},
                            warnings=[str(exc)],
                        )
                if isinstance(parsed, dict):
                    structured_query = parsed
            result = excel_query_service.query_rows(
                file_id=selected["file_id"],
                structured_query=structured_query,
                natural_query=query,
                return_mode=return_mode,
                sample_limit=sample_limit,
                export=export,
            )
            data = result.get("data", {})
            data["selected_file"] = selected
            warnings = result.get("warnings", [])
            generated_outputs = result.get("generated_outputs", [])
            return ok_response(
                "auto_query_spreadsheet_rows",
                "Sorgu basariyla tamamlandi.",
                data,
                files=[item["path"] for item in generated_outputs if isinstance(item, dict) and item.get("path")] or [],
                warnings=warnings,
                generated_outputs=generated_outputs,
            )

        return tool_handler("auto_query_spreadsheet_rows", run)

    @mcp.tool()
    def auto_filter_excel_rows(
        query: str,
        file_query: str = "",
        category: str = "excel",
        limit: int = 50,
        export: bool = False,
    ) -> str:
        """File_id istemeden uygun Excel dosyasini bulur ve dogal sorguyla satir filtreler."""

        def run():
            excel_service.scan_uploads()
            selected = excel_service.select_file(file_query or query, category)
            if not selected:
                return ok_response(
                    "auto_filter_excel_rows",
                    "Uygun Excel dosyasi bulunamadi.",
                    {"query": query, "file_query": file_query, "category": category},
                    warnings=["Ilgili klasore dosya ekleyin veya refresh_file_library calistirin."],
                )
            data = excel_compare_service.filter_rows(selected["file_id"], query=query, limit=limit, export=export)
            data["selected_file"] = selected
            files = data.pop("files", [])
            return ok_response("auto_filter_excel_rows", "Excel satir filtresi tamamlandi.", data, files=files)

        return tool_handler("auto_filter_excel_rows", run)

    @mcp.tool()
    def auto_compare_excel_changes(
        file_query_a: str = "",
        file_query_b: str = "",
        key_query: str = "email tc kimlik aday id",
        column_query: str = "form durum iletim",
        from_value: str = "",
        to_value: str = "",
        limit: int = 50,
        export: bool = False,
    ) -> str:
        """File_id istemeden iki Excel arasinda aday/form durum degisimlerini bulur."""

        def run():
            excel_service.scan_uploads()
            matches = excel_service.find_files("", "excel")["matches"]
            first = excel_service.select_file(file_query_a, "excel")
            second = excel_service.select_file(file_query_b, "excel") if file_query_b else None
            if not second and len(matches) >= 2:
                second = next((item for item in matches if not first or item["file_id"] != first["file_id"]), None)
            if not first or not second:
                return ok_response(
                    "auto_compare_excel_changes",
                    "Karsilastirma icin iki Excel dosyasi bulunamadi.",
                    {"available_excel_files": matches},
                    warnings=["Iki farkli Excel dosyasini data/uploads/excel klasorune koyun."],
                )
            data = excel_compare_service.compare_column_changes(
                first["file_id"],
                second["file_id"],
                key_query,
                column_query,
                from_value,
                to_value,
                limit,
                export,
            )
            data["selected_files"] = {"a": first, "b": second}
            files = data.pop("files", [])
            return ok_response("auto_compare_excel_changes", "Excel degisim karsilastirmasi tamamlandi.", data, files=files)

        return tool_handler("auto_compare_excel_changes", run)

    @mcp.tool()
    def summarize_spreadsheet_column(file_id: str, column: str = "", query: str = "", limit: int = 30) -> str:
        """Bir kolondaki deger dagilimini ozetler."""

        return tool_handler(
            "summarize_spreadsheet_column",
            lambda: ok_response(
                "summarize_spreadsheet_column",
                "Kolon dagilimi ozetlendi.",
                excel_compare_service.summarize_column(file_id, column, query, limit),
            ),
        )

    @mcp.tool()
    def find_duplicate_rows(file_id: str, key_columns: str = "", keep: str = "first") -> str:
        """Dosyada duplicate kayitlari bulur."""

        return tool_handler(
            "find_duplicate_rows",
            lambda: ok_response("find_duplicate_rows", "Duplicate analizi tamamlandi.", excel_compare_service.find_duplicates(file_id, key_columns, keep)),
        )

    @mcp.tool()
    def deduplicate_spreadsheet(file_id: str, key_columns: str = "", keep: str = "first", export: bool = True) -> str:
        """Duplicate kayitlari temizler; yeni file_id ve opsiyonel Excel ciktisi uretir."""

        def run():
            data = excel_compare_service.deduplicate_file(file_id, key_columns, keep, export)
            files = data.pop("files", [])
            return ok_response("deduplicate_spreadsheet", "Tekillestirme tamamlandi.", data, files=files)

        return tool_handler("deduplicate_spreadsheet", run)

    @mcp.tool()
    def clear_spreadsheet_registry(file_id: str = "") -> str:
        """Yuklu dosyayi veya tum registry'yi temizler."""

        target = file_id or None
        return tool_handler(
            "clear_spreadsheet_registry",
            lambda: ok_response("clear_spreadsheet_registry", "Registry temizlendi.", excel_service.clear_file(target)),
        )
