"""Analytics-service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="analytics-service", alias="SERVICE_NAME")

    # Owner DSN — analytics reads cross-tenant (see ADR-017).
    database_url_admin: str = Field(..., alias="DATABASE_URL_ADMIN")

    # MV refresh
    mv_refresh_interval_seconds: int = Field(300, alias="ANALYTICS_MV_REFRESH_INTERVAL")
    mv_refresh_enabled: bool = Field(default=True, alias="ANALYTICS_MV_REFRESH_ENABLED")

    # Cache
    cache_ttl_seconds: int = Field(default=60, alias="ANALYTICS_CACHE_TTL")

    # Alerts
    alerts_enabled: bool = Field(default=True, alias="ANALYTICS_ALERTS_ENABLED")
    alert_reply_rate_threshold: float = Field(default=0.02, alias="ANALYTICS_ALERT_REPLY_RATE")
    alert_bounce_rate_threshold: float = Field(default=0.05, alias="ANALYTICS_ALERT_BOUNCE_RATE")
    alert_window_hours: int = Field(default=24, alias="ANALYTICS_ALERT_WINDOW_HOURS")
    alert_check_interval_seconds: int = Field(3600, alias="ANALYTICS_ALERT_CHECK_INTERVAL")
