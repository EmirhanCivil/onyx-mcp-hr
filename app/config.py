"""Application configuration for Survey & Excel Intelligence MCP."""

from __future__ import annotations

import os
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Runtime settings loaded from environment variables."""

    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads")))
    CV_UPLOAD_DIR: Path = Path(os.getenv("CV_UPLOAD_DIR", str(UPLOAD_DIR / "cv")))
    EXCEL_UPLOAD_DIR: Path = Path(os.getenv("EXCEL_UPLOAD_DIR", str(UPLOAD_DIR / "excel")))
    SURVEY_UPLOAD_DIR: Path = Path(os.getenv("SURVEY_UPLOAD_DIR", str(UPLOAD_DIR / "survey")))
    PROCESSED_DIR: Path = Path(os.getenv("PROCESSED_DIR", str(DATA_DIR / "processed")))
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(DATA_DIR / "outputs")))
    CHART_DIR: Path = Path(os.getenv("CHART_DIR", str(OUTPUT_DIR / "charts")))
    REPORT_DIR: Path = Path(os.getenv("REPORT_DIR", str(OUTPUT_DIR / "reports")))
    EXPORT_DIR: Path = Path(os.getenv("EXPORT_DIR", str(OUTPUT_DIR / "exports")))
    LOG_DIR: Path = Path(os.getenv("LOG_DIR", str(BASE_DIR / "logs")))

    MCP_HOST: str = os.getenv("MCP_HOST", "127.0.0.1")
    MCP_PORT: int = int(os.getenv("MCP_PORT", "8005"))
    MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "sse")
    MCP_PATH: str = os.getenv("MCP_PATH", "/sse" if MCP_TRANSPORT == "sse" else "/mcp")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEFAULT_MIN_GROUP_SIZE: int = int(os.getenv("DEFAULT_MIN_GROUP_SIZE", "5"))
    MAX_PREVIEW_ROWS: int = int(os.getenv("MAX_PREVIEW_ROWS", "50"))
    LARGE_FILE_ROW_THRESHOLD: int = int(os.getenv("LARGE_FILE_ROW_THRESHOLD", "100000"))

    AUTO_LOAD_ENABLED: bool = _bool_env("AUTO_LOAD_ENABLED", False)
    AUTO_EXCEL_PATH: str = os.getenv("AUTO_EXCEL_PATH", "")
    AUTO_SCAN_UPLOADS_ENABLED: bool = _bool_env("AUTO_SCAN_UPLOADS_ENABLED", True)

    SUPPORTED_SPREADSHEET_EXTENSIONS: set[str] = {".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".csv"}
    SUPPORTED_CV_EXTENSIONS: set[str] = {".txt", ".docx", ".pdf", ".csv", ".xlsx", ".xls"}

    SURVEY_GROUP_HINTS: set[str] = {
        "birim",
        "departman",
        "department",
        "unit",
        "ekip",
        "lokasyon",
        "location",
        "unvan",
        "title",
        "yonetici",
    }


settings = Settings()


def ensure_directories() -> None:
    """Create runtime directories used by upload, export, chart, and report jobs."""

    for path in (
        settings.DATA_DIR,
        settings.UPLOAD_DIR,
        settings.CV_UPLOAD_DIR,
        settings.EXCEL_UPLOAD_DIR,
        settings.SURVEY_UPLOAD_DIR,
        settings.PROCESSED_DIR,
        settings.OUTPUT_DIR,
        settings.CHART_DIR,
        settings.REPORT_DIR,
        settings.EXPORT_DIR,
        settings.LOG_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
