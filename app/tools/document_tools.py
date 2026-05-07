"""Generic document creation MCP tool — any format from a single call."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from app.core.exceptions import AppError
from app.core.response_schema import ok_response, tool_handler
from app.services.document_service import document_service


def _parse_content(content: Any) -> dict[str, Any]:
    if content is None or content == "":
        return {}
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AppError("BAD_CONTENT", f"content JSON parse hatası: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise AppError("BAD_CONTENT", "content JSON bir nesne (object) olmalı.")
        return parsed
    raise AppError("BAD_CONTENT", "content dict veya JSON string olmalı.")


def register_document_tools(mcp: FastMCP) -> None:
    """Register the generic document creation tool."""

    @mcp.tool()
    def create_document(
        format: str,
        filename: str = "",
        title: str = "",
        content: Any = None,
        page_size: str = "A4",
    ) -> str:
        """Tek çağrıda istenen formatta dosya üretir; chat'e indirme linki döner.

        Desteklenen formatlar: xlsx, csv, tsv, txt, md, html, json, docx, pdf

        İçerik şeması (`content`, dict veya JSON string olabilir):
          • xlsx: {"sheets":[{"name":"Sayfa1","columns":["A","B"],"rows":[[1,2]]}]}
                  veya {"columns":[...],"rows":[[...]]}
          • csv: {"columns":[...],"rows":[[...]]} — default ayraç `;` + UTF-8 BOM
                  (Türkçe Excel uyumlu, karakterler bozulmaz). `,` istiyorsan
                  {"delimiter":","} ekle.
          • tsv: {"columns":[...],"rows":[[...]]} — sekme ayraçlı
          • txt: {"text":"..."} veya {"lines":["...","..."]}
          • json: {"data": <herhangi bir yapı>}
          • md / html: {"markdown":"..."} veya {"html":"..."} (sadece html için)
                       veya {"sections":[{"heading":"...","level":2,"body":"...",
                                          "bullets":["..."],"table":{"columns":[],"rows":[[]]}}]}
          • docx / pdf: {"sections":[{"heading":"...","level":1,"body":"...",
                                       "bullets":[...],"numbered":[...],
                                       "table":{"columns":[],"rows":[[]]}}]}
                        veya {"text":"..."} / {"paragraphs":[...]}

        Args:
            format: Çıktı formatı (xlsx/csv/tsv/txt/md/html/json/docx/pdf).
            filename: Çıktı dosya adı (uzantı eksikse otomatik eklenir).
            title: Başlık — docx/pdf/html/md başlığı olarak kullanılır.
            content: Format-spesifik içerik (yukarıdaki şema).
            page_size: PDF sayfa boyutu (A4|LETTER|LEGAL|A3|A5).

        Örnek 1 — 3x3 çarpım tablosu (xlsx):
            create_document(format="xlsx",
              filename="carpim_3x3",
              title="3x3 Çarpım Tablosu",
              content={"sheets":[{"name":"Çarpım",
                "columns":["x","1","2","3"],
                "rows":[[1,1,2,3],[2,2,4,6],[3,3,6,9]]}]})

        Örnek 2 — Yönetici özeti (pdf):
            create_document(format="pdf",
              filename="ozet",
              title="Aylık Yönetici Özeti",
              content={"sections":[
                {"heading":"Genel","body":"Toplam 5500 başvuru..."},
                {"heading":"Departman dağılımı",
                 "table":{"columns":["Bölüm","Sayı"],"rows":[["BM",420],["EE",312]]}}
              ]})

        Örnek 3 — Sade not (txt):
            create_document(format="txt",
              filename="notlar",
              content={"text":"İlk satır\\nİkinci satır"})
        """

        def run():
            payload = _parse_content(content)
            result = document_service.create(
                format=format,
                filename=filename,
                title=title,
                content=payload,
                page_size=page_size,
            )
            output = {
                "type": "document",
                "title": result["title"] or result["filename"],
                "description": f"{result['format'].upper()} dokümanı",
                "format": result["format"],
                "path": result["path"],
            }
            return ok_response(
                "create_document",
                f"{result['format'].upper()} dosyası oluşturuldu: {result['filename']}",
                {
                    "format": result["format"],
                    "filename": result["filename"],
                    "path": result["path"],
                    "title": result["title"],
                    "meta": result["meta"],
                },
                files=[result["path"]],
                generated_outputs=[output],
            )

        return tool_handler("create_document", run)
