"""Telegram-sender settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="telegram-sender", alias="SERVICE_NAME")
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")

    # Fernet key for encrypting bot tokens / session strings
    telegram_encryption_key: str = Field(..., alias="TELEGRAM_ENCRYPTION_KEY")

    dry_run: bool = Field(default=True, alias="TELEGRAM_DRY_RUN")

    # Rate limits (jitter hard)
    daily_limit_max: int = Field(default=30, alias="TELEGRAM_DAILY_LIMIT_MAX")
    hourly_limit_max: int = Field(default=5, alias="TELEGRAM_HOURLY_LIMIT_MAX")

    # NATS
    nats_durable_name: str = Field(default="telegram-sender", alias="NATS_DURABLE_NAME")
