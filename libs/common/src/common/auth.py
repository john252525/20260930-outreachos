"""Service-token authentication for service-to-service / BFF calls.

Enforcement is opt-in: if ``SERVICE_TOKEN`` is not configured in the service
environment, the check is a no-op (dev). When set, callers must send
``Authorization: Bearer <token>``.
"""

import os

from fastapi import Header, HTTPException, status


async def require_service_token(authorization: str | None = Header(None)) -> None:
    expected = os.environ.get("SERVICE_TOKEN")
    if not expected:
        if os.environ.get("ENV", "dev") == "dev":
            return
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SERVICE_TOKEN not configured",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing service token"
        )
    token = authorization.removeprefix("Bearer ")
    if token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid service token")
