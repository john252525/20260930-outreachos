"""WhatsApp-sender settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="whatsapp-sender", alias="SERVICE_NAME")
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")
    tenant_service_url: str = Field(
        default="http://tenant-service:8000", alias="TENANT_SERVICE_URL"
    )

    whatsapp_encryption_key: str = Field(..., alias="WHATSAPP_ENCRYPTION_KEY")
    dry_run: bool = Field(default=True, alias="WHATSAPP_DRY_RUN")
    enabled: bool = Field(default=False, alias="WHATSAPP_ENABLED")

    default_provider: str = Field(default="gupshup", alias="WHATSAPP_DEFAULT_PROVIDER")
    session_window_hours: int = Field(default=24, alias="WHATSAPP_WINDOW_HOURS")

    nats_durable_name: str = Field(default="whatsapp-sender", alias="NATS_DURABLE_NAME")
