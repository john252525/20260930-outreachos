"""Event emission helpers for icp-service."""

from typing import Any
from uuid import UUID

from icp_service.models import ICP
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


def _correlation(brief_id: str) -> UUID | None:
    try:
        return UUID(brief_id)
    except (ValueError, TypeError):
        return None


def _payload(icp: ICP) -> dict[str, Any]:
    return {
        "icp": {
            "id": str(icp.id),
            "brief_id": icp.brief_id,
            "version": icp.version,
            "segments_count": icp.segments_count,
        }
    }


async def emit_icp_generated(publisher: Publisher, icp: ICP, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.ICP_GENERATED,
        tenant_id=icp.tenant_id,
        payload=_payload(icp),
        trace_id=trace_id,
        correlation_id=_correlation(icp.brief_id),
    )


async def emit_icp_revised(publisher: Publisher, icp: ICP, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.ICP_REVISED,
        tenant_id=icp.tenant_id,
        payload=_payload(icp),
        trace_id=trace_id,
        correlation_id=_correlation(icp.brief_id),
    )
