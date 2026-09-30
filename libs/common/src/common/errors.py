"""Application error hierarchy."""

from typing import Any


class AppError(Exception):
    """Base application error."""

    code: str = "internal_error"
    status_code: int = 500
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details: dict[str, Any] = details or {}


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404
    message = "Resource not found"


class ConflictError(AppError):
    code = "conflict"
    status_code = 409
    message = "Conflict"


class ValidationError(AppError):
    code = "validation_error"
    status_code = 422
    message = "Validation failed"


class TenantMismatchError(AppError):
    code = "tenant_mismatch"
    status_code = 403
    message = "Tenant mismatch"
