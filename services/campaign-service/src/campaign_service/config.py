"""Campaign-service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="campaign-service", alias="SERVICE_NAME")
    analytics_service_url: str = Field(
        default="http://analytics-service:8000", alias="ANALYTICS_SERVICE_URL"
    )
    orchestrator_url: str = Field(default="http://orchestrator:8000", alias="ORCHESTRATOR_URL")
