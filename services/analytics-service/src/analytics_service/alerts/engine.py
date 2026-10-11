"""Alert engine: flags low reply rate / high bounce rate per tenant."""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import structlog

from analytics_service.config import Settings
from analytics_service.events import emit_alert
from analytics_service.repository import MetricsRepository
from nats_client.publisher import Publisher

logger = structlog.get_logger()

MIN_SENT_FOR_REPLY_ALERT = 50
MIN_SENT_FOR_BOUNCE_ALERT = 20


class AlertEngine:
    def __init__(self, repo: MetricsRepository, publisher: Publisher, settings: Settings) -> None:
        self._repo = repo
        self._publisher = publisher
        self._settings = settings

    async def check_all(self, *, tenant_id: UUID) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        today = date.today()
        days = max(1, self._settings.alert_window_hours // 24)
        from_date = today - timedelta(days=days)

        overview = await self._repo.overview(
            tenant_id=tenant_id, from_date=from_date, to_date=today
        )
        sent = int(overview.get("sent", 0))
        reply_rate = float(overview.get("reply_rate", 0.0))
        if sent >= MIN_SENT_FOR_REPLY_ALERT and (
            reply_rate < self._settings.alert_reply_rate_threshold
        ):
            alerts.append(
                {
                    "type": "low_reply_rate",
                    "value": float(overview.get("reply_rate", 0.0)),
                    "threshold": self._settings.alert_reply_rate_threshold,
                    "message": (
                        f"Reply rate {overview.get('reply_rate', 0.0):.2%} ниже порога "
                        f"{self._settings.alert_reply_rate_threshold:.2%}"
                    ),
                }
            )
        bounce_rate = float(overview.get("bounce_rate", 0.0))
        if sent >= MIN_SENT_FOR_BOUNCE_ALERT and (
            bounce_rate > self._settings.alert_bounce_rate_threshold
        ):
            alerts.append(
                {
                    "type": "high_bounce_rate",
                    "value": float(overview.get("bounce_rate", 0.0)),
                    "threshold": self._settings.alert_bounce_rate_threshold,
                    "message": (
                        f"Bounce rate {overview.get('bounce_rate', 0.0):.2%} выше порога "
                        f"{self._settings.alert_bounce_rate_threshold:.2%}"
                    ),
                }
            )

        for a in alerts:
            await emit_alert(self._publisher, tenant_id=tenant_id, alert=a)
            logger.warning("analytics_alert", tenant_id=str(tenant_id), **a)
        return alerts

    async def check_tenants(self, tenant_ids: list[UUID]) -> int:
        total = 0
        for tid in tenant_ids:
            try:
                total += len(await self.check_all(tenant_id=tid))
            except Exception as e:
                logger.exception("alert_check_failed", tenant_id=str(tid), error=str(e))
        return total
