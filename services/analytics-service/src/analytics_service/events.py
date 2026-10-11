"""Event emission helpers for analytics-service."""

from uuid import UUID

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects


async def emit_alert(
    publisher: Publisher, *, tenant_id: UUID, alert: dict[str, object], trace_id: str = ""
) -> None:
    value = alert.get("value", 0.0)
    threshold = alert.get("threshold", 0.0)
    await publisher.publish(
        Subjects.ANALYTICS_ALERT,
        tenant_id=tenant_id,
        payload={
            "alert_type": str(alert.get("type", "")),
            "value": float(str(value)) if value is not None else 0.0,
            "threshold": float(str(threshold)) if threshold is not None else 0.0,
            "message": str(alert.get("message", "")),
        },
        trace_id=trace_id,
    )
