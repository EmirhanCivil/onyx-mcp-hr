"""Domain exceptions with stable error codes for MCP responses."""

from __future__ import annotations


class AppError(Exception):
    """Base application error with a machine-readable code."""

    code = "APP_ERROR"

    def __init__(self, detail: str, code: str | None = None):
        super().__init__(detail)
        if code:
            self.code = code
        self.detail = detail


class FileNotRegisteredError(AppError):
    code = "FILE_NOT_REGISTERED"


class InvalidInputError(AppError):
    code = "INVALID_INPUT"


class FileProcessingError(AppError):
    code = "FILE_PROCESSING_ERROR"


class ColumnNotFoundError(AppError):
    code = "COLUMN_NOT_FOUND"
