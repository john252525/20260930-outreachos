"""Provider registry."""

from llm_gateway.config import Settings
from llm_gateway.providers.base import LLMProvider
from llm_gateway.providers.deepseek import DeepSeekProvider
from llm_gateway.providers.mock import MockProvider


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self._providers: dict[str, LLMProvider] = {
            "deepseek": DeepSeekProvider(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=float(settings.llm_timeout_seconds),
            ),
            "mock": MockProvider(),
        }
        self._default = settings.default_provider

    def get(self, name: str) -> LLMProvider:
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        return self._providers[name]

    def resolve(self, model: str) -> LLMProvider:
        """Route a request to a provider based on the model name.

        ``mock*`` -> mock, ``deepseek*`` -> deepseek, otherwise the default.
        """
        if model == "mock" or model.startswith("mock-"):
            return self.get("mock")
        if model.startswith("deepseek"):
            return self.get("deepseek")
        return self.get(self._default)

    def default(self) -> LLMProvider:
        return self.get(self._default)

    async def close(self) -> None:
        for provider in self._providers.values():
            await provider.close()
