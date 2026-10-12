"""LinkedIn-sender settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="linkedin-sender", alias="SERVICE_NAME")
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")
    tenant_service_url: str = Field(
        default="http://tenant-service:8000", alias="TENANT_SERVICE_URL"
    )

    # Fernet key for encrypting LinkedIn secrets
    linkedin_encryption_key: str = Field(..., alias="LINKEDIN_ENCRYPTION_KEY")

    # Safety: never send for real unless explicitly enabled
    dry_run: bool = Field(default=True, alias="LINKEDIN_DRY_RUN")
    # Global kill-switch: LinkedIn disabled entirely unless enabled
    enabled: bool = Field(default=False, alias="LINKEDIN_ENABLED")

    # Rate limits (very conservative)
    daily_limit_max: int = Field(default=20, alias="LINKEDIN_DAILY_LIMIT_MAX")
    weekly_limit_max: int = Field(default=80, alias="LINKEDIN_WEEKLY_LIMIT_MAX")

    # Human behavior jitter
    min_action_delay_seconds: float = Field(default=20.0, alias="LINKEDIN_MIN_DELAY")
    max_action_delay_seconds: float = Field(default=60.0, alias="LINKEDIN_MAX_DELAY")

    # NATS
    nats_durable_name: str = Field(default="linkedin-sender", alias="NATS_DURABLE_NAME")
