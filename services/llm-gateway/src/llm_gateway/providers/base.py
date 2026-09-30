"""Provider abstraction for LLM backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    task_type: str
    system: str | None
    user: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    json_mode: bool = False


@dataclass
class LLMResponse:
    """Provider output. Providers report tokens only; cost is computed centrally."""

    text: str
    model: str
    tokens_in_cache_hit: int
    tokens_in_cache_miss: int
    tokens_out: int
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_in(self) -> int:
        return self.tokens_in_cache_hit + self.tokens_in_cache_miss


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, req: LLMRequest) -> LLMResponse: ...

    async def close(self) -> None:
        return None
