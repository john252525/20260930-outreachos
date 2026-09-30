"""DeepSeek LLM provider (OpenAI-compatible API).

Reports token counts only; cost computation lives in ``llm_gateway.pricing``.
"""

import time

import httpx

from llm_gateway.providers.base import LLMProvider, LLMRequest, LLMResponse


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(self, api_key: str, base_url: str, *, timeout: float = 180.0) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    async def complete(self, req: LLMRequest) -> LLMResponse:
        if not self._api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        messages: list[dict[str, str]] = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.user})

        payload: dict[str, object] = {
            "model": req.model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        latency_ms = int((time.monotonic() - started) * 1000)

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        cache_hit = int(usage.get("prompt_cache_hit_tokens", 0))
        cache_miss = usage.get("prompt_cache_miss_tokens")
        if cache_miss is None:
            cache_miss = max(prompt_tokens - cache_hit, 0)
        cache_miss = int(cache_miss)

        return LLMResponse(
            text=text,
            model=str(data.get("model", req.model)),
            tokens_in_cache_hit=cache_hit,
            tokens_in_cache_miss=cache_miss,
            tokens_out=completion_tokens,
            latency_ms=latency_ms,
            raw=data,
        )

    async def close(self) -> None:
        await self._client.aclose()
