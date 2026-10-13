"""Realtime-gateway settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="realtime-gateway", alias="SERVICE_NAME")
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    presence_ttl_seconds: int = Field(default=60, alias="REALTIME_PRESENCE_TTL")
    nats_durable_name: str = Field(default="realtime-gateway", alias="NATS_DURABLE_NAME")
