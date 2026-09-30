"""Idempotency middleware backed by Redis.

Requires an ``Idempotency-Key`` header on mutating requests. When the same key
is seen again (for the same tenant) within TTL, the stored response is
replayed.
"""

import json
from collections.abc import AsyncIterator

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from common.redis import get_redis

IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
IGNORED_PATHS = {"/healthz", "/readyz"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, ttl_seconds: int = 86400) -> None:
        super().__init__(app)
        self._ttl = ttl_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in IDEMPOTENT_METHODS:
            return await call_next(request)
        if request.url.path in IGNORED_PATHS:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        try:
            redis = get_redis()
        except RuntimeError:
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID", "no-tenant")
        cache_key = f"idem:{tenant_id}:{key}"

        cached = await redis.get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            return JSONResponse(
                content=data["body"],
                status_code=data["status"],
                headers={"X-Idempotent-Replay": "true"},
            )

        response = await call_next(request)

        body_bytes = b""
        async for chunk in _iter_body(response):
            body_bytes += chunk
        try:
            body_json = json.loads(body_bytes) if body_bytes else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            body_json = None

        if 200 <= response.status_code < 300 and body_json is not None:
            await redis.setex(
                cache_key,
                self._ttl,
                json.dumps({"status": response.status_code, "body": body_json}),
            )

        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


async def _iter_body(response: Response) -> AsyncIterator[bytes]:
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is not None:
        async for chunk in body_iterator:
            if isinstance(chunk, str):
                yield chunk.encode()
            else:
                yield chunk
    else:
        body = getattr(response, "body", b"")
        yield body
