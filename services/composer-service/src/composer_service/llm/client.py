"""Wrapper around llm-gateway for icp-service."""

import hashlib
from typing import Any, TypeVar

import httpx
import structlog
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from common.errors import AppError
from composer_service.config import Settings
from composer_service.llm.json_utils import LLMJSONError, parse_json_strict

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class LLMGatewayError(AppError):
    """Raised when llm-gateway call fails or returns invalid data."""

    code = "llm_error"
    status_code = 502


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.llm_gateway_url,
            timeout=httpx.Timeout(300.0, connect=10.0),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def complete(
        self,
        *,
        tenant_id: str,
        task_type: str,
        system: str | None,
        user: str,
        trace_id: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        use_cache: bool = False,
    ) -> str:
        payload = {
            "task_type": task_type,
            "system": system,
            "user": user,
            "model": self._settings.llm_model,
            "temperature": temperature
            if temperature is not None
            else self._settings.llm_temperature,
            "max_tokens": max_tokens or self._settings.llm_max_tokens,
            "json_mode": json_mode,
            "use_cache": use_cache,
        }
        prompt_hash = hashlib.sha256(user.encode()).hexdigest()[:16]
        response = await self._client.post(
            "/v1/complete",
            json=payload,
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
                "Idempotency-Key": f"{task_type}:{trace_id}:{prompt_hash}",
            },
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return str(data["text"])

    async def complete_json(
        self,
        *,
        tenant_id: str,
        task_type: str,
        system: str,
        user: str,
        output_schema: type[T],
        trace_id: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        raw = await self.complete(
            tenant_id=tenant_id,
            task_type=task_type,
            system=system,
            user=user,
            trace_id=trace_id,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            use_cache=False,
        )
        try:
            parsed = parse_json_strict(raw)
        except LLMJSONError as e:
            logger.warning(
                "llm_json_parse_failed", task=task_type, error=str(e), raw_preview=raw[:500]
            )
            raise LLMGatewayError(str(e)) from e
        try:
            return output_schema.model_validate(parsed)
        except ValidationError as e:
            logger.warning("llm_schema_validation_failed", task=task_type, error=str(e))
            raise LLMGatewayError(f"LLM output failed schema validation: {e}") from e

    async def close(self) -> None:
        await self._client.aclose()
