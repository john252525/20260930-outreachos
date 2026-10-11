"""Sender-email settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="sender-email", alias="SERVICE_NAME")
    composer_service_url: str = Field(
        default="http://composer-service:8000", alias="COMPOSER_SERVICE_URL"
    )
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")

    # Password encryption (Fernet key)
    sender_encryption_key: str = Field(..., alias="SENDER_ENCRYPTION_KEY")

    # Safety
    dry_run: bool = Field(default=True, alias="SENDER_DRY_RUN")

    # IMAP poller
    imap_poll_interval_seconds: int = Field(default=300, alias="SENDER_IMAP_POLL_INTERVAL")
    imap_poller_enabled: bool = Field(default=False, alias="SENDER_IMAP_POLLER_ENABLED")

    # Retry
    max_deliver: int = Field(default=20, alias="SENDER_MAX_DELIVER")
