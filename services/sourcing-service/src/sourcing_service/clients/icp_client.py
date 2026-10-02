"""HTTP client to icp-service."""

from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from common.errors import AppError

logger = structlog.get_logger()


class ICPNotFoundError(AppError):
    code = "icp_not_found"
    status_code = 404
    message = "ICP not found"


class ICPClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def get_icp(self, icp_id: str, *, tenant_id: str, trace_id: str = "") -> dict[str, Any]:
        resp = await self._client.get(
            f"/icps/{icp_id}",
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        if resp.status_code == 404:
            raise ICPNotFoundError(f"ICP {icp_id} not found")
        resp.raise_for_status()
        return dict[str, Any](resp.json())

    async def close(self) -> None:
        await self._client.aclose()
