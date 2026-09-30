"""Tenant-ID middleware."""

from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from common.context import reset_tenant_id, set_tenant_id

DEFAULT_SKIP_PATHS = {"/healthz", "/readyz", "/docs", "/openapi.json", "/redoc", "/"}


class TenantMiddleware(BaseHTTPMiddleware):
    """Reads X-Tenant-ID and puts it into contextvars.

    Some endpoints are exempt (health, docs) or explicitly (e.g. POST /tenants
    that creates a new tenant before it has an id).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        skip_paths: set[str] | None = None,
        skip_rules: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(app)
        self._skip_paths = skip_paths if skip_paths is not None else DEFAULT_SKIP_PATHS
        self._skip_rules = skip_rules or []

    def _is_skipped(self, request: Request) -> bool:
        path = request.url.path
        if path in self._skip_paths:
            return True
        for method, rule_path in self._skip_rules:
            if request.method == method and path == rule_path:
                return True
        return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._is_skipped(request):
            return await call_next(request)

        raw = request.headers.get("X-Tenant-ID")
        if raw is None:
            return JSONResponse(
                {"error": "missing_tenant", "message": "X-Tenant-ID header required"},
                status_code=400,
            )
        try:
            tenant_id = UUID(raw)
        except ValueError:
            return JSONResponse(
                {"error": "invalid_tenant", "message": "X-Tenant-ID must be a UUID"},
                status_code=400,
            )
        token = set_tenant_id(tenant_id)
        try:
            return await call_next(request)
        finally:
            reset_tenant_id(token)
