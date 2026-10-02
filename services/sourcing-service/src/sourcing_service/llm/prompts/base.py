"""Base prompt primitives for sourcing-service."""

from dataclasses import dataclass

PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM_NORMALIZER = """Ты — эксперт по нормализации данных о компаниях из результатов поиска.

Правила:
- Отвечай ТОЛЬКО валидным JSON, без markdown-обёрток и пояснений.
- Если данных нет — используй null или пустой массив. Не выдумывай.
- Названия компаний и должности — на языке оригинала.
- Confidence: 0.9+ — если явно в заголовке; 0.7-0.9 — если в сниппете; 0.5-0.7 — вывод; <0.5 — не уверен.
- Evidence обязателен для каждого поля. source_url = URL кандидата."""
