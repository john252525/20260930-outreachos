"""Contact-store settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="contact-store", alias="SERVICE_NAME")

    # Dedup
    enable_fuzzy_company_match: bool = Field(default=False, alias="CONTACT_STORE_FUZZY_MATCH")

    # Stop-list
    global_stoplist_enabled: bool = Field(default=True, alias="CONTACT_STORE_GLOBAL_STOPLIST")

    # Bulk
    bulk_max_size: int = Field(default=500, alias="CONTACT_STORE_BULK_MAX")
