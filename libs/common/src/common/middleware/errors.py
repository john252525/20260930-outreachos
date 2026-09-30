"""Exception handlers producing a consistent JSON error shape."""

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from common.errors import AppError

logger = structlog.get_logger()


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        code=exc.code,
        status=exc.status_code,
        message=exc.message,
        path=str(request.url.path),
    )
    return JSONResponse(
        {"error": exc.code, "message": exc.message, "details": exc.details},
        status_code=exc.status_code,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", path=str(request.url.path))
    return JSONResponse(
        {"error": "internal_error", "message": "Internal server error"},
        status_code=500,
    )
