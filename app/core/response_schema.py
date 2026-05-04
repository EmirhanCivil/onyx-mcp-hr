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
    outputs = list(generated_outputs or [])
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
            "json": "application/json",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(suffix, "application/octet-stream")
        outputs.append({
            "type": output_type,
            "title": path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1],
            "description": "",
            "format": suffix or "file",
            "path": path,
            "mime_type": mime,
            "display": output_type in {"chart", "report"} or suffix in {"png", "html", "md"},
        })
    return outputs
