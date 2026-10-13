"""Users-service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="users-service", alias="SERVICE_NAME")

    database_url_admin: str = Field(default="", alias="DATABASE_URL_ADMIN")
    tenant_service_url: str = Field(
        default="http://tenant-service:8000", alias="TENANT_SERVICE_URL"
    )

    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_expires_minutes: int = Field(default=10080, alias="JWT_EXPIRES_MINUTES")

    # brute-force
    max_failed_logins: int = Field(default=5, alias="USERS_MAX_FAILED_LOGINS")
    lock_minutes: int = Field(default=15, alias="USERS_LOCK_MINUTES")
