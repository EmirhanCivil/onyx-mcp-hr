"""Standard JSON response helpers for MCP tools."""

from __future__ import annotations

import json
import traceback
from typing import Any, Callable

from app.core.exceptions import AppError
from app.logging_config import logger


def ok_response(
    tool_name: str,
    message: str,
    data: Any = None,
    files: list[str] | None = None,
    charts: list[str] | None = None,
    warnings: list[str] | None = None,
    generated_outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    outputs = [_enrich_output(item) for item in (generated_outputs or []) if isinstance(item, dict)]
    known_paths = {item.get("path") for item in outputs if isinstance(item, dict)}
    outputs.extend([item for item in _path_outputs(files or [], "file") if item["path"] not in known_paths])
    known_paths = {item.get("path") for item in outputs if isinstance(item, dict)}
    outputs.extend([item for item in _path_outputs(charts or [], "chart") if item["path"] not in known_paths])
    return {
        "status": "success",
        "success": True,
        "tool_name": tool_name,
        "message": message,
        "data": data or {},
        "files": files or [],
        "charts": charts or [],
        "generated_outputs": outputs,
        "warnings": warnings or [],
        "errors": [],
    }


def error_response(
    tool_name: str,
    message: str,
    code: str,
    detail: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "success": False,
        "tool_name": tool_name,
        "message": message,
        "data": None,
        "files": [],
        "charts": [],
        "generated_outputs": [],
        "warnings": warnings or [],
        "errors": [{"code": code, "detail": detail}],
    }


def to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def tool_handler(tool_name: str, fn: Callable[[], dict[str, Any]]) -> str:
    """Run a tool body and serialize a standard response."""

    try:
        return to_json(fn())
    except AppError as exc:
        logger.warning("%s failed: %s", tool_name, exc.detail)
        return to_json(error_response(tool_name, "İşlem başarısız.", exc.code, exc.detail))
    except Exception as exc:
        logger.error("%s unexpected failure: %s\n%s", tool_name, exc, traceback.format_exc())
        return to_json(error_response(tool_name, "İşlem başarısız.", "UNEXPECTED_ERROR", str(exc)))


_PUBLIC_FILES_BASE = "http://localhost:8007"


def _to_public_url(local_path: str) -> str:
    p = (local_path or "").replace("\\", "/")
    if "/app/data/outputs/" in p:
        return p.replace("/app/data/outputs", _PUBLIC_FILES_BASE)
    return local_path


def _markdown_for(path: str, title: str, suffix: str, url: str) -> str:
    if suffix == "png":
        return f"![{title}]({url})"
    icons = {
        "xlsx": "📊",
        "csv": "📊",
        "tsv": "📊",
        "docx": "📑",
        "json": "🧾",
        "html": "📄",
        "md": "📝",
        "txt": "📄",
        "pdf": "📕",
    }
    icon = icons.get(suffix, "📎")
    label = f"{icon} {title}" if suffix not in {"png"} else title
    return f"[{label}]({url})"


def _enrich_output(item: dict[str, Any]) -> dict[str, Any]:
    """Add url/public_url/markdown to a generated_outputs item if missing."""
    out = dict(item)
    path = out.get("path", "")
    if not path:
        return out
    suffix = (out.get("format") or path.rsplit(".", 1)[-1] if "." in path else "").lower()
    title = out.get("title") or path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    url = out.get("url") or _to_public_url(path)
    out.setdefault("url", url)
    out.setdefault("public_url", url)
    if not out.get("markdown"):
        out["markdown"] = _markdown_for(path, title, suffix, url)
    return out


def _path_outputs(paths: list[str], output_type: str) -> list[dict[str, Any]]:
    outputs = []
    for path in paths:
        if not isinstance(path, str):
            continue
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        mime = {
            "png": "image/png",
            "html": "text/html",
            "md": "text/markdown",
            "txt": "text/plain",
            "csv": "text/csv",
            "tsv": "text/tab-separated-values",
            "json": "application/json",
            "pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(suffix, "application/octet-stream")
        title = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        url = _to_public_url(path)
        outputs.append({
            "type": output_type,
            "title": title,
            "description": "",
            "format": suffix or "file",
            "path": path,
            "url": url,
            "public_url": url,
            "markdown": _markdown_for(path, title, suffix, url),
            "mime_type": mime,
            "display": output_type in {"chart", "report", "document"} or suffix in {"png", "html", "md", "xlsx", "docx", "csv", "tsv", "txt", "pdf", "json"},
        })
    return outputs
