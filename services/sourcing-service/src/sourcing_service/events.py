"""Event emission helpers for sourcing-service."""

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from sourcing_service.models import SearchJob


async def emit_contacts_search_started(
    publisher: Publisher, job: SearchJob, *, sources: list[str], trace_id: str
) -> None:
    await publisher.publish(
        Subjects.CONTACTS_SEARCH_STARTED,
        tenant_id=job.tenant_id,
        payload={
            "icp_id": str(job.icp_id),
            "segment_id": job.segment_id,
            "sources": sources,
        },
        trace_id=trace_id,
        correlation_id=job.id,
    )


async def emit_contacts_found(
    publisher: Publisher,
    job: SearchJob,
    *,
    count: int,
    company_ids: list[str],
    contact_ids: list[str],
    trace_id: str,
) -> None:
    await publisher.publish(
        Subjects.CONTACTS_FOUND,
        tenant_id=job.tenant_id,
        payload={
            "icp_id": str(job.icp_id),
            "segment_id": job.segment_id,
            "count": count,
            "company_ids": company_ids,
            "contact_ids": contact_ids,
            "search_job_id": str(job.id),
        },
        trace_id=trace_id,
        correlation_id=job.id,
    )


async def emit_contacts_enriched(
    publisher: Publisher, job: SearchJob, *, contact_ids: list[str], trace_id: str
) -> None:
    await publisher.publish(
        Subjects.CONTACTS_ENRICHED,
        tenant_id=job.tenant_id,
        payload={"contact_ids": contact_ids},
        trace_id=trace_id,
        correlation_id=job.id,
    )
