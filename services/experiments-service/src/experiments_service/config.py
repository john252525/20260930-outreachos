"""Experiments-service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="experiments-service", alias="SERVICE_NAME")

    database_url_admin: str = Field(default="", alias="DATABASE_URL_ADMIN")
    analytics_service_url: str = Field(
        default="http://analytics-service:8000", alias="ANALYTICS_SERVICE_URL"
    )
    evaluate_interval_seconds: int = Field(default=3600, alias="EXPERIMENTS_EVALUATE_INTERVAL")
    auto_evaluate_enabled: bool = Field(default=True, alias="EXPERIMENTS_AUTO_EVALUATE")
