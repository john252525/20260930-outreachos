"""Business logic for the LLM gateway."""

from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common.context import get_trace_id
from common.errors import AppError
from db.rls import set_tenant_context
from llm_gateway.cache import cache_get, cache_set, prompt_hash
from llm_gateway.langfuse_client import LangfuseClient
from llm_gateway.models import LLMCall
from llm_gateway.pricing import compute_cost, is_peak
from llm_gateway.providers.base import LLMRequest, LLMResponse
from llm_gateway.providers.registry import ProviderRegistry
from llm_gateway.schemas import CompleteRequest, CompleteResponse

logger = structlog.get_logger()


class LLMGatewayService:
    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        session: AsyncSession,
        redis: "Redis[str]",
        langfuse: LangfuseClient | None,
        cache_ttl: int,
        tenant_id: UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._registry = registry
        self._session = session
        self._redis = redis
        self._langfuse = langfuse
        self._cache_ttl = cache_ttl
        self._tenant_id = tenant_id
        self._session_factory = session_factory

    async def complete(self, req: CompleteRequest) -> CompleteResponse:
        trace_id = get_trace_id() or ""
        provider = self._registry.resolve(req.model)
        ph = prompt_hash(req, provider.name)

        if req.use_cache:
            cached = await cache_get(self._redis, ph)
            if cached is not None:
                logger.info("llm_cache_hit", task=req.task_type, prompt_hash=ph)
                payload = {**cached, "cached": True}
                return CompleteResponse(**payload)

        try:
            result = await provider.complete(
                LLMRequest(
                    task_type=req.task_type,
                    system=req.system,
                    user=req.user,
                    model=req.model,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    json_mode=req.json_mode,
                )
            )
        except Exception as e:
            logger.exception("llm_provider_failed", task=req.task_type)
            await self._record_error(req, ph, provider.name, str(e), trace_id)
            raise AppError(f"LLM provider failed: {e}", code="llm_error", status_code=502) from e

        cost_usd = compute_cost(
            model=result.model,
            tokens_in_cache_hit=result.tokens_in_cache_hit,
            tokens_in_cache_miss=result.tokens_in_cache_miss,
            tokens_out=result.tokens_out,
        )

        response = CompleteResponse(
            text=result.text,
            model=result.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=cost_usd,
            latency_ms=result.latency_ms,
        )

        await self._record_success(req, ph, provider.name, result, cost_usd, trace_id)

        if req.use_cache:
            await cache_set(self._redis, ph, response.model_dump(), ttl=self._cache_ttl)

        if self._langfuse is not None:
            self._langfuse.trace_generation(
                name=req.task_type,
                tenant_id=str(self._tenant_id),
                trace_id=trace_id,
                input_data={"system": req.system, "user": req.user},
                output_data={"text": result.text},
                model=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=cost_usd,
                latency_ms=result.latency_ms,
            )

        return response

    async def _record_success(
        self,
        req: CompleteRequest,
        ph: str,
        provider_name: str,
        result: LLMResponse,
        cost_usd: float,
        trace_id: str,
    ) -> None:
        self._session.add(
            LLMCall(
                tenant_id=self._tenant_id,
                task_type=req.task_type,
                provider=provider_name,
                model=result.model,
                prompt_hash=ph,
                tokens_in=result.tokens_in,
                tokens_in_cache_hit=result.tokens_in_cache_hit,
                tokens_in_cache_miss=result.tokens_in_cache_miss,
                tokens_out=result.tokens_out,
                is_peak=is_peak(),
                cost_usd=cost_usd,
                latency_ms=result.latency_ms,
                cached=False,
                request_body={"system": req.system, "user": req.user, "model": req.model},
                response_text=result.text,
                langfuse_trace_id=trace_id or None,
            )
        )
        await self._session.flush()

    async def _record_error(
        self,
        req: CompleteRequest,
        ph: str,
        provider_name: str,
        error: str,
        trace_id: str,
    ) -> None:
        """Record a failed call in its own transaction so it survives rollback."""
        try:
            async with self._session_factory() as session, session.begin():
                await set_tenant_context(session, self._tenant_id)
                session.add(
                    LLMCall(
                        tenant_id=self._tenant_id,
                        task_type=req.task_type,
                        provider=provider_name,
                        model=req.model,
                        prompt_hash=ph,
                        tokens_in=0,
                        tokens_in_cache_hit=0,
                        tokens_in_cache_miss=0,
                        tokens_out=0,
                        is_peak=is_peak(),
                        cost_usd=0,
                        latency_ms=0,
                        cached=False,
                        request_body={
                            "system": req.system,
                            "user": req.user,
                            "model": req.model,
                        },
                        response_text="",
                        error=error,
                        langfuse_trace_id=trace_id or None,
                    )
                )
        except Exception:
            logger.exception("llm_error_record_failed")
