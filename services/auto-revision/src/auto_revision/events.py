"""Event emission helpers for auto-revision."""

from auto_revision.models import Revision
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_revision_proposed(
    publisher: Publisher, revision: Revision, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.REVISION_PROPOSED,
        tenant_id=revision.tenant_id,
        payload={
            "revision": {
                "id": str(revision.id),
                "template_id": revision.template_id,
                "trigger_type": revision.trigger_type,
            }
        },
        trace_id=trace_id,
        correlation_id=revision.id,
    )


async def emit_revision_approved(
    publisher: Publisher, revision: Revision, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.REVISION_APPROVED,
        tenant_id=revision.tenant_id,
        payload={
            "revision_id": str(revision.id),
            "experiment_id": str(revision.experiment_id) if revision.experiment_id else None,
        },
        trace_id=trace_id,
        correlation_id=revision.id,
    )


async def emit_revision_rejected(
    publisher: Publisher, revision: Revision, *, trace_id: str
) -> None:
    await publisher.publish(
        Subjects.REVISION_REJECTED,
        tenant_id=revision.tenant_id,
        payload={"revision_id": str(revision.id), "reason": revision.rejection_reason or ""},
        trace_id=trace_id,
        correlation_id=revision.id,
    )
