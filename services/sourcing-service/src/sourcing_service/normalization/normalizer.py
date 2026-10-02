"""LLM-based normalization of raw candidates."""

import asyncio
import json
from uuid import UUID

import structlog

from common.context import get_trace_id
from sourcing_service.connectors.base import RawCandidate
from sourcing_service.llm.client import LLMClient
from sourcing_service.llm.prompts.normalize_candidate import build_normalize_prompt
from sourcing_service.llm.schemas import NormalizedCandidate

logger = structlog.get_logger()


class Normalizer:
    """Turns a RawCandidate into a structured Company + Contacts via LLM."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def normalize(
        self,
        candidate: RawCandidate,
        *,
        tenant_id: UUID,
        segment_context: str,
    ) -> NormalizedCandidate:
        extra = None
        if candidate.source in ("registry", "enricher", "website_parser"):
            extra = json.dumps(candidate.raw_payload, ensure_ascii=False, indent=2)[:2000]
        prompt = build_normalize_prompt(
            candidate_title=candidate.title,
            candidate_snippet=candidate.snippet,
            candidate_url=candidate.source_url,
            candidate_domain=candidate.domain,
            segment_context=segment_context,
            candidate_extra=extra,
        )
        return await self._llm.complete_json(
            tenant_id=str(tenant_id),
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=NormalizedCandidate,
            trace_id=get_trace_id() or "",
        )

    async def normalize_batch(
        self,
        candidates: list[RawCandidate],
        *,
        tenant_id: UUID,
        segment_context: str,
        max_concurrency: int = 5,
    ) -> list[tuple[RawCandidate, NormalizedCandidate | None, str | None]]:
        """Normalize a batch concurrently: [(candidate, result|None, error|None)]."""
        sem = asyncio.Semaphore(max_concurrency)
        results: list[tuple[RawCandidate, NormalizedCandidate | None, str | None]] = []

        async def _one(
            c: RawCandidate,
        ) -> tuple[RawCandidate, NormalizedCandidate | None, str | None]:
            async with sem:
                try:
                    r = await self.normalize(
                        c, tenant_id=tenant_id, segment_context=segment_context
                    )
                    return (c, r, None)
                except Exception as e:
                    logger.warning("normalize_failed", candidate=c.source_url, error=str(e))
                    return (c, None, str(e))

        tasks = [_one(c) for c in candidates]
        for coro in asyncio.as_completed(tasks):
            results.append(await coro)
        return results
