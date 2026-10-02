"""LLM personalization: rendered template -> email draft."""

import structlog

from composer_service.config import Settings
from composer_service.llm.client import LLMClient
from composer_service.llm.schemas import GeneratedEmail
from composer_service.templates.base import RenderedTemplate, Template

logger = structlog.get_logger()


class Personalizer:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def generate(
        self,
        *,
        tenant_id: str,
        rendered: RenderedTemplate,
        template: Template,
        trace_id: str = "",
    ) -> tuple[str | None, str, list[str]]:
        """Returns (subject, body, warnings)."""
        result = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type=f"composer_{template.template_id}_{template.template_version}",
            system=rendered.system_prompt,
            user=rendered.user_prompt,
            output_schema=GeneratedEmail,
            trace_id=trace_id,
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )

        warnings = template.validate_output(subject=result.subject, body=result.body)
        if warnings:
            logger.warning(
                "composer_output_warnings",
                warnings=warnings,
                template=template.template_id,
            )
        return result.subject, result.body, warnings
