"""Central logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import ensure_directories, settings


def configure_logging() -> logging.Logger:
    """Configure and return the application logger."""

    ensure_directories()
    logger = logging.getLogger("survey_excel_mcp")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        settings.LOG_DIR / "survey_excel_mcp.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = configure_logging()
