"""Optional Langfuse integration (SDK v4 / OpenTelemetry based).

If the SDK is unavailable or keys are absent, all calls are no-ops.
Cost is computed by us (see ``llm_gateway.pricing``) and passed to Langfuse
explicitly, so Langfuse and our database always agree.
"""

from __future__ import annotations

import contextlib
from typing import Any

import structlog

logger = structlog.get_logger()


class LangfuseClient:
    """Thin wrapper around the Langfuse SDK."""

    def __init__(self, public_key: str, secret_key: str, base_url: str) -> None:
        self._enabled = bool(public_key and secret_key)
        self._client: Any = None
        if not self._enabled:
            return
        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                base_url=base_url,
            )
        except Exception as e:
            logger.warning("langfuse_init_failed", error=str(e))
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def trace_generation(
        self,
        *,
        name: str,
        tenant_id: str,
        trace_id: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        latency_ms: int,
    ) -> None:
        if not self._enabled or self._client is None:
            return
        try:
            trace_context = None
            if trace_id:
                try:
                    trace_context = self._client.create_trace_id(seed=trace_id)
                except Exception:
                    trace_context = None

            obs = self._client.start_observation(
                name=name,
                as_type="generation",
                trace_context={"trace_id": trace_context} if trace_context else None,
                input=input_data,
                output=output_data,
                model=model,
                usage_details={
                    "input": tokens_in,
                    "output": tokens_out,
                    "total": tokens_in + tokens_out,
                },
                cost_details={"total": cost_usd},
                metadata={
                    "tenant_id": tenant_id,
                    "latency_ms": latency_ms,
                },
            )
            obs.end()
        except Exception as e:
            logger.warning("langfuse_trace_failed", error=str(e))

    def flush(self) -> None:
        if self._enabled and self._client is not None:
            with contextlib.suppress(Exception):
                self._client.flush()
