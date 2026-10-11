"""Event emission helpers for experiments-service."""

from experiments_service.models import Experiment
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_experiment_created(
    publisher: Publisher, experiment: Experiment, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.EXPERIMENT_CREATED,
        tenant_id=experiment.tenant_id,
        payload={
            "experiment_id": str(experiment.id),
            "name": experiment.name,
            "variants_count": len(experiment.variants or []),
        },
        trace_id=trace_id,
        correlation_id=experiment.id,
    )


async def emit_variant_won(
    publisher: Publisher, experiment: Experiment, variant_id: str, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.EXPERIMENT_VARIANT_WON,
        tenant_id=experiment.tenant_id,
        payload={
            "experiment_id": str(experiment.id),
            "variant_id": variant_id,
        },
        trace_id=trace_id,
        correlation_id=experiment.id,
    )
