"""Sourcing service settings."""

from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field(default="sourcing-service", alias="SERVICE_NAME")
    icp_service_url: str = Field(default="http://icp-service:8000", alias="ICP_SERVICE_URL")
    contact_store_url: str = Field(default="http://contact-store:8000", alias="CONTACT_STORE_URL")
    llm_gateway_url: str = Field(default="http://llm-gateway:8000", alias="LLM_GATEWAY_URL")

    # Serper (Google Search API)
    serper_api_key: str = Field(default="", alias="SERPER_API_KEY")
    serper_base_url: str = Field(default="https://google.serper.dev", alias="SERPER_BASE_URL")
    serper_rate_limit_per_sec: float = Field(default=5.0, alias="SERPER_RATE_LIMIT_PER_SEC")

    # Yandex XML
    yandex_xml_user: str = Field(default="", alias="YANDEX_XML_USER")
    yandex_xml_key: str = Field(default="", alias="YANDEX_XML_KEY")
    yandex_xml_rate_limit_per_day: int = Field(default=1000, alias="YANDEX_XML_RATE_LIMIT_PER_DAY")

    # LLM
    llm_model: str = Field(default="deepseek-flash", alias="SOURCING_LLM_MODEL")
    llm_temperature: float = Field(default=0.2, alias="SOURCING_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, alias="SOURCING_LLM_MAX_TOKENS")

    # Sourcing limits
    max_candidates_per_source: int = Field(default=50, alias="SOURCING_MAX_CANDIDATES_PER_SOURCE")
    max_sources_per_search: int = Field(default=5, alias="SOURCING_MAX_SOURCES_PER_SEARCH")
    min_score_threshold: float = Field(default=0.5, alias="SOURCING_MIN_SCORE")

    # Concurrency
    max_parallel_sources: int = Field(default=3, alias="SOURCING_MAX_PARALLEL_SOURCES")
    max_parallel_llm: int = Field(default=5, alias="SOURCING_MAX_PARALLEL_LLM")

    # Reliability
    job_timeout_seconds: int = Field(default=1800, alias="SOURCING_JOB_TIMEOUT")

    # Registry (DaData)
    dadata_api_key: str = Field(default="", alias="DADATA_API_KEY")
    dadata_secret_key: str = Field(default="", alias="DADATA_SECRET_KEY")

    # Enricher (Hunter)
    hunter_api_key: str = Field(default="", alias="HUNTER_API_KEY")
