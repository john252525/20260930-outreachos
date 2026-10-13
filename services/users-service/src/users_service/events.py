"""Event emission helpers for users-service."""

from uuid import UUID

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_user_created(
    publisher: Publisher, *, tenant_id: UUID, user_id: UUID, email: str, trace_id: str = ""
) -> None:
    await publisher.publish(
        Subjects.TENANT_UPDATED,
        tenant_id=tenant_id,
        payload={"tenant": {"id": str(tenant_id), "name": "user_created", "status": "active"}},
        trace_id=trace_id,
    )
