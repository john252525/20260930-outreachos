"""Base settings shared by all services."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Base configuration. Each service subclasses and adds fields."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    service_name: str = Field(default="service", alias="SERVICE_NAME")
    service_port: int = Field(default=8000, alias="SERVICE_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    env: str = Field(default="dev", alias="ENV")

    database_url: str = Field(..., alias="DATABASE_URL")
    nats_url: str = Field(..., alias="NATS_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"
