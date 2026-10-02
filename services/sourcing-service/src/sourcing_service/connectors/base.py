"""Connector abstraction: raw candidate types and the Connector interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class RawCandidate:
    """A raw candidate from a connector. Not normalized, not scored."""

    source: str
    source_url: str | None
    title: str | None = None
    snippet: str | None = None
    domain: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict[str, Any])
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def dedup_key(self) -> str:
        if self.domain:
            return f"domain:{self.domain.lower()}"
        if self.source_url:
            return f"url:{self.source_url.lower()}"
        return f"title:{self.title}:{self.source}"


@dataclass
class SearchCriteria:
    """Search criteria, built by the orchestrator from an ICP segment."""

    keywords: list[str]
    negative_keywords: list[str] = field(default_factory=list)
    geo: list[str] = field(default_factory=list)
    language: str = "ru"
    limit: int = 50
    domain_whitelist: list[str] | None = None
    domain_blacklist: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class ConnectorResult:
    """Result of a connector run."""

    source: str
    candidates: list[RawCandidate]
    cost_usd: float = 0.0
    error: str | None = None
    duration_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict[str, Any])


class Connector(ABC):
    """Base connector. A connector ONLY fetches data. It does not normalize,
    score, or write to the database."""

    name: str

    def __init__(self, *, rate_limit_per_sec: float = 5.0, timeout: float = 30.0) -> None:
        self._rate_limit = rate_limit_per_sec
        self._timeout = timeout

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> ConnectorResult: ...

    async def close(self) -> None:
        return None

    @property
    def is_available(self) -> bool:
        return True

    @property
    def cost_per_call_usd(self) -> float:
        return 0.0
