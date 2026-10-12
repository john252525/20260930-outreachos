"""Business logic for auto-revision."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from auto_revision.analysis.llm_advisor import LLMAdvisor
from auto_revision.analysis.metrics_analyzer import MetricsAnalyzer
from auto_revision.analysis.template_revisor import TemplateRevisor
from auto_revision.clients.composer_client import ComposerClient
from auto_revision.clients.experiments_client import ExperimentsClient
from auto_revision.config import Settings
from auto_revision.events import (
    emit_revision_approved,
    emit_revision_proposed,
    emit_revision_rejected,
)
from auto_revision.models import Revision
from auto_revision.repository import RevisionRepository
from common.errors import NotFoundError, ValidationError
from nats_client.publisher import Publisher

logger = structlog.get_logger()

# Baseline system prompt / user template for the default template (fallback).
FALLBACK_SYSTEM = (
    "Ты — опытный B2B sales copywriter. Пиши персонализированные холодные письма. "
    'Отвечай только JSON: {"subject": "...", "body": "..."}.'
)
FALLBACK_USER = (
    "Сгенерируй письмо для {{ contact_name }} ({{ company_name }}). "
    "Что продаём: {{ what_we_sell }}. Подпись: {{ sender_name }}."
)


class RevisionService:
    def __init__(
        self,
        *,
        repo: RevisionRepository,
        analyzer: MetricsAnalyzer,
        advisor: LLMAdvisor,
        revisor: TemplateRevisor,
        composer: ComposerClient,
        experiments: ExperimentsClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._analyzer = analyzer
        self._advisor = advisor
        self._revisor = revisor
        self._composer = composer
        self._experiments = experiments
        self._publisher = publisher
        self._settings = settings

    async def propose(
        self,
        *,
        tenant_id: UUID,
        trigger_type: str,
        trigger_context: dict[str, Any],
        trace_id: str = "",
    ) -> Revision:
        window_days = trigger_context.get("window_days")
        metrics = await self._analyzer.analyze(tenant_id=tenant_id, window_days=window_days)

        template_id = trigger_context.get("template_id") or self._analyzer.find_worst_template(
            metrics
        )
        if not template_id:
            template_id = "email_cold_outreach"

        existing = await self._repo.find_pending_for_template(tenant_id, template_id)
        if existing is not None:
            logger.info("revision_already_pending", revision_id=str(existing.id))
            return existing

        diagnosis = await self._advisor.diagnose(
            tenant_id=str(tenant_id),
            metrics=metrics,
            template_id=template_id,
            sample_emails=[],
            trace_id=trace_id,
        )
        confidence = float(diagnosis.get("llm_confidence", 0.0))
        if confidence < self._settings.min_confidence:
            raise ValidationError(
                f"Low confidence in diagnosis ({confidence}); no revision proposed"
            )

        proposed_changes = diagnosis.get("proposed_changes", []) or []
        revised = await self._revisor.revise(
            tenant_id=str(tenant_id),
            template_id=template_id,
            original_system=FALLBACK_SYSTEM,
            original_user_template=FALLBACK_USER,
            diagnosis=str(diagnosis.get("diagnosis", "")),
            proposed_changes=[dict(c) for c in proposed_changes],
            trace_id=trace_id,
        )

        revision = Revision(
            tenant_id=tenant_id,
            trigger_type=trigger_type,
            trigger_context={**trigger_context, "metrics": metrics.as_dict()},
            template_id=template_id,
            template_version="v1",
            segment_id=trigger_context.get("segment_id"),
            status="pending",
            diagnosis=str(diagnosis.get("diagnosis", "")),
            proposed_changes=[dict(c) for c in proposed_changes],
            proposed_template={
                "system_prompt": revised.get("system_prompt", ""),
                "user_prompt_template": revised.get("user_prompt_template", ""),
                "variables_used": revised.get("variables_used", []),
                "summary": revised.get("summary", ""),
            },
            llm_model=self._settings.llm_model,
            llm_confidence=confidence,
        )
        await self._repo.add(revision)
        await self._repo.session.refresh(revision)
        await emit_revision_proposed(self._publisher, revision, trace_id=trace_id)
        logger.info(
            "revision_proposed",
            revision_id=str(revision.id),
            template_id=template_id,
            confidence=confidence,
        )
        return revision

    async def approve(
        self,
        *,
        tenant_id: UUID,
        revision_id: UUID,
        user_id: str,
        trace_id: str = "",
    ) -> Revision:
        revision = await self.get(revision_id)
        if revision.status != "pending":
            raise ValidationError(f"Cannot approve revision with status {revision.status}")

        override_version = f"auto-{revision.id.hex[:8]}"
        await self._composer.create_template_override(
            tenant_id=str(tenant_id),
            template_id=revision.template_id,
            base_version=revision.template_version,
            override_version=override_version,
            system_prompt=str(revision.proposed_template.get("system_prompt", "")),
            user_prompt_template=str(revision.proposed_template.get("user_prompt_template", "")),
            source_revision_id=str(revision.id),
            trace_id=trace_id,
            idempotency_key=f"revision:{revision.id}:override",
        )

        changes = revision.proposed_changes or []
        variable_type = str(changes[0].get("variable_type", "body")) if changes else "body"
        experiment = await self._experiments.create_experiment(
            tenant_id=str(tenant_id),
            data={
                "name": f"Auto-revision {revision.id.hex[:8]}",
                "hypothesis": revision.diagnosis or "auto-revision",
                "variable_type": variable_type
                if variable_type in ("subject", "body", "offer", "cta", "tone")
                else "body",
                "variable_description": str(changes[0].get("description", "")) if changes else "",
                "channel": "email",
                "variants": [
                    {
                        "id": "control",
                        "name": "Control",
                        "template_id": revision.template_id,
                        "weight": 0.5,
                    },
                    {
                        "id": "variant",
                        "name": "Variant",
                        "template_id": revision.template_id,
                        "weight": 0.5,
                    },
                ],
                "metrics": {"primary": "positive_reply_rate", "secondary": ["reply_rate"]},
                "sample_size_per_variant": self._settings.experiment_sample_size_per_variant,
            },
            trace_id=trace_id,
            idempotency_key=f"revision:{revision.id}:experiment",
        )

        revision.status = "approved"
        revision.reviewed_by = user_id
        revision.reviewed_at = datetime.now(UTC)
        revision.experiment_id = UUID(str(experiment["id"]))
        revision.override_version = override_version
        await self._flush(revision)
        await emit_revision_approved(self._publisher, revision, trace_id=trace_id)
        logger.info(
            "revision_approved",
            revision_id=str(revision.id),
            experiment_id=str(revision.experiment_id),
        )
        return revision

    async def reject(
        self,
        *,
        revision_id: UUID,
        user_id: str,
        reason: str,
        trace_id: str = "",
    ) -> Revision:
        revision = await self.get(revision_id)
        if revision.status != "pending":
            raise ValidationError(f"Cannot reject revision with status {revision.status}")
        revision.status = "rejected"
        revision.reviewed_by = user_id
        revision.reviewed_at = datetime.now(UTC)
        revision.rejection_reason = reason
        await self._flush(revision)
        await emit_revision_rejected(self._publisher, revision, trace_id=trace_id)
        return revision

    async def get(self, revision_id: UUID) -> Revision:
        revision = await self._repo.get(revision_id)
        if revision is None:
            raise NotFoundError(f"Revision {revision_id} not found")
        return revision

    async def list(
        self, *, tenant_id: UUID, status: str | None, limit: int, offset: int
    ) -> list[Revision]:
        return await self._repo.list_all(
            tenant_id=tenant_id, status=status, limit=limit, offset=offset
        )

    async def _flush(self, revision: Revision) -> None:
        await self._repo.session.flush()
        await self._repo.session.refresh(revision)
