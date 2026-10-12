"""LLM advisor: produce a diagnosis from metrics."""

from typing import Any

import structlog

from auto_revision.analysis.metrics_analyzer import MetricsSnapshot
from auto_revision.llm.client import LLMClient
from auto_revision.llm.prompts.diagnose import build_diagnose_prompt
from auto_revision.llm.schemas import Diagnosis

logger = structlog.get_logger()


class LLMAdvisor:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def diagnose(
        self,
        *,
        tenant_id: str,
        metrics: MetricsSnapshot,
        template_id: str,
        sample_emails: list[str],
        trace_id: str = "",
    ) -> dict[str, Any]:
        prompt = build_diagnose_prompt(
            metrics=metrics, template_id=template_id, sample_emails=sample_emails
        )
        result: Diagnosis = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=Diagnosis,
            trace_id=trace_id,
            temperature=0.3,
            max_tokens=4096,
        )
        logger.info(
            "revision_diagnosed",
            confidence=result.llm_confidence,
            changes=len(result.proposed_changes),
        )
        return result.model_dump()
