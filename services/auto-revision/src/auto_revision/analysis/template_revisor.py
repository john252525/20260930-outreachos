"""LLM template revisor: generate a new template version."""

from typing import Any

import structlog

from auto_revision.llm.client import LLMClient
from auto_revision.llm.prompts.revise import build_revise_prompt
from auto_revision.llm.schemas import RevisedTemplate

logger = structlog.get_logger()


class TemplateRevisor:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def revise(
        self,
        *,
        tenant_id: str,
        template_id: str,
        original_system: str,
        original_user_template: str,
        diagnosis: str,
        proposed_changes: list[dict[str, str]],
        trace_id: str = "",
    ) -> dict[str, Any]:
        prompt = build_revise_prompt(
            template_id=template_id,
            original_system=original_system,
            original_user_template=original_user_template,
            diagnosis=diagnosis,
            proposed_changes=proposed_changes,
        )
        result: RevisedTemplate = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=RevisedTemplate,
            trace_id=trace_id,
            temperature=0.5,
            max_tokens=8192,
        )
        logger.info("template_revised", summary=result.summary)
        return result.model_dump()
