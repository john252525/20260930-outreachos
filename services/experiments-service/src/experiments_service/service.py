"""Business logic for experiments-service."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from common.errors import ConflictError, NotFoundError, ValidationError
from experiments_service.clients.analytics_client import AnalyticsClient
from experiments_service.config import Settings
from experiments_service.engine.bandit import ThompsonSampling
from experiments_service.engine.stats_engine import StatsEngine
from experiments_service.engine.variant_assigner import VariantAssigner
from experiments_service.events import emit_experiment_created, emit_variant_won
from experiments_service.models import Experiment
from experiments_service.repository import ExperimentRepository
from experiments_service.schemas import AssignResponse, ExperimentCreate
from nats_client.publisher import Publisher

logger = structlog.get_logger()

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"running"},
    "running": {"paused", "completed", "aborted"},
    "paused": {"running", "completed", "aborted"},
}


class ExperimentService:
    def __init__(
        self,
        *,
        repo: ExperimentRepository,
        analytics: AnalyticsClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._analytics = analytics
        self._publisher = publisher
        self._settings = settings

    async def create(
        self, *, tenant_id: UUID, data: ExperimentCreate, trace_id: str = ""
    ) -> Experiment:
        total = sum(v.weight for v in data.variants)
        if abs(total - 1.0) > 1e-6:
            raise ValidationError(f"Variant weights must sum to 1.0, got {total}")

        existing = await self._repo.get_by_name(tenant_id, data.name)
        if existing is not None:
            raise ConflictError(f"Experiment '{data.name}' already exists")

        experiment = Experiment(
            tenant_id=tenant_id,
            name=data.name,
            hypothesis=data.hypothesis,
            status="draft",
            segment_id=data.segment_id,
            channel=data.channel,
            icp_version=data.icp_version,
            variable_type=data.variable_type,
            variable_description=data.variable_description,
            variants=[v.model_dump() for v in data.variants],
            metrics=data.metrics.model_dump(),
            sample_size_target=data.sample_size_target,
            sample_size_per_variant=data.sample_size_per_variant,
            confidence_level=data.confidence_level,
            minimum_detectable_effect=data.minimum_detectable_effect,
            allocation_strategy=data.allocation_strategy,
            results={},
        )
        await self._repo.add(experiment)
        await self._repo.session.refresh(experiment)
        await emit_experiment_created(self._publisher, experiment, trace_id=trace_id)
        logger.info(
            "experiment_created",
            experiment_id=str(experiment.id),
            variants=len(experiment.variants),
        )
        return experiment

    async def start(self, *, tenant_id: UUID, experiment_id: UUID) -> Experiment:
        exp = await self.get(experiment_id)
        self._require_transition(exp, "running")
        exp.status = "running"
        exp.started_at = datetime.now(UTC)
        await self._flush(exp)
        return exp

    async def pause(self, *, tenant_id: UUID, experiment_id: UUID) -> Experiment:
        exp = await self.get(experiment_id)
        self._require_transition(exp, "paused")
        exp.status = "paused"
        await self._flush(exp)
        return exp

    async def evaluate(
        self, *, tenant_id: UUID, experiment_id: UUID, trace_id: str = ""
    ) -> Experiment:
        exp = await self.get(experiment_id)
        if exp.status not in ("running", "paused"):
            return exp

        rows = await self._analytics.get_experiment_variants_for(
            tenant_id=str(tenant_id), experiment_id=experiment_id, trace_id=trace_id
        )
        by_variant = {str(r.get("variant_id")): r for r in rows}
        variants_data: list[dict[str, Any]] = []
        for v in exp.variants or []:
            row = by_variant.get(str(v.get("id")), {})
            variants_data.append(
                {
                    "variant_id": str(v.get("id")),
                    "sent": int(row.get("sent", 0) or 0),
                    "replied": int(row.get("replied", 0) or 0),
                    "positive_replied": int(row.get("positive_replied", 0) or 0),
                    "meetings_booked": int(row.get("meetings_booked", 0) or 0),
                }
            )

        engine = StatsEngine(confidence_level=exp.confidence_level)
        result = engine.compute(
            variants_data=variants_data,
            primary_metric=(exp.metrics or {}).get("primary", "positive_reply_rate"),
            sample_size_per_variant=exp.sample_size_per_variant,
            minimum_detectable_effect=exp.minimum_detectable_effect,
        )

        exp.results = {
            "variants": [
                {
                    "variant_id": s.variant_id,
                    "sent": s.sent,
                    "replied": s.replied,
                    "positive_replied": s.positive_replied,
                    "meetings_booked": s.meetings_booked,
                    "primary_metric_value": s.primary_metric_value,
                    "confidence_interval": list(s.confidence_interval),
                }
                for s in result.variants
            ],
            "winner_variant_id": result.winner_variant_id,
            "is_significant": result.is_significant,
            "p_value": result.p_value,
            "reason": result.reason,
            "concluded_at": (datetime.now(UTC).isoformat() if result.is_significant else None),
        }
        await self._flush(exp)

        if result.is_significant and result.winner_variant_id:
            await emit_variant_won(
                self._publisher, exp, result.winner_variant_id, trace_id=trace_id
            )
            exp.status = "completed"
            exp.finished_at = datetime.now(UTC)
            await self._flush(exp)
            logger.info(
                "experiment_completed",
                experiment_id=str(exp.id),
                winner=result.winner_variant_id,
                p_value=result.p_value,
            )
        return exp

    async def assign(
        self, *, tenant_id: UUID, experiment_id: UUID, contact_id: UUID
    ) -> AssignResponse:
        exp = await self.get(experiment_id)
        variant_id: str | None
        if exp.status == "completed" and exp.results.get("winner_variant_id"):
            variant_id = str(exp.results["winner_variant_id"])
        elif exp.status in ("draft", "running", "paused"):
            if exp.allocation_strategy == "thompson" and exp.status == "running":
                stats = exp.results.get("variants") or []
                if stats:
                    variant_id = ThompsonSampling.choose_variant(stats)
                else:
                    assigner = VariantAssigner()
                    variant_id = assigner.assign(
                        experiment_id=str(exp.id),
                        contact_id=str(contact_id),
                        variants=exp.variants or [],
                    )
            else:
                assigner = VariantAssigner()
                variant_id = assigner.assign(
                    experiment_id=str(exp.id),
                    contact_id=str(contact_id),
                    variants=exp.variants or [],
                )
        else:
            win = exp.results.get("winner_variant_id")
            variant_id = str(win) if win else None

        template_id: str | None = None
        for v in exp.variants or []:
            if str(v.get("id")) == variant_id:
                template_id = v.get("template_id") or None
                break

        return AssignResponse(
            experiment_id=exp.id,
            contact_id=contact_id,
            variant_id=variant_id,
            template_id=template_id,
        )

    async def get(self, experiment_id: UUID) -> Experiment:
        exp = await self._repo.get(experiment_id)
        if exp is None:
            raise NotFoundError(f"Experiment {experiment_id} not found")
        return exp

    async def list(
        self, *, tenant_id: UUID, status: str | None, limit: int, offset: int
    ) -> list[Experiment]:
        return await self._repo.list_all(
            tenant_id=tenant_id, status=status, limit=limit, offset=offset
        )

    async def evaluate_running(self, *, tenant_id: UUID) -> int:
        count = 0
        for exp in await self._repo.list_running(tenant_id):
            try:
                await self.evaluate(tenant_id=tenant_id, experiment_id=exp.id)
                count += 1
            except Exception as e:  # pragma: no cover - defensive
                logger.exception("auto_evaluate_failed", experiment_id=str(exp.id), error=str(e))
        return count

    @staticmethod
    def _require_transition(exp: Experiment, target: str) -> None:
        allowed = VALID_TRANSITIONS.get(exp.status, set())
        if target not in allowed:
            raise ValidationError(f"Cannot transition experiment from {exp.status} to {target}")

    async def _flush(self, exp: Experiment) -> None:
        await self._repo.session.flush()
        await self._repo.session.refresh(exp)

    @staticmethod
    def default_window() -> tuple[date, date]:
        today = date.today()
        return today - timedelta(days=30), today
