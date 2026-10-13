"""ML-scoring settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="ml-scoring-service", alias="SERVICE_NAME")
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")
    min_samples_for_scoring: int = Field(default=1000, alias="ML_MIN_SAMPLES")
