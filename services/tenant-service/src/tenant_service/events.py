"""Event emission helpers for tenant-service."""

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from tenant_service.models import Tenant


async def emit_tenant_created(publisher: Publisher, tenant: Tenant, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.TENANT_CREATED,
        tenant_id=tenant.id,
        payload={"tenant": {"id": str(tenant.id), "name": tenant.name, "status": tenant.status}},
        trace_id=trace_id,
    )


async def emit_tenant_updated(publisher: Publisher, tenant: Tenant, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.TENANT_UPDATED,
        tenant_id=tenant.id,
        payload={"tenant": {"id": str(tenant.id), "name": tenant.name, "status": tenant.status}},
        trace_id=trace_id,
    )


async def emit_tenant_archived(publisher: Publisher, tenant: Tenant, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.TENANT_ARCHIVED,
        tenant_id=tenant.id,
        payload={"tenant": {"id": str(tenant.id), "name": tenant.name, "status": "archived"}},
        trace_id=trace_id,
    )


async def emit_tenant_restored(publisher: Publisher, tenant: Tenant, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.TENANT_RESTORED,
        tenant_id=tenant.id,
        payload={"tenant": {"id": str(tenant.id), "name": tenant.name, "status": "active"}},
        trace_id=trace_id,
    )
