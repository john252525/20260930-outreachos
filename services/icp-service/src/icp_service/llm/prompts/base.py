"""Base prompt primitives for icp-service."""

from dataclasses import dataclass

PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM_COMMON = """Ты — эксперт по B2B-маркетингу и сегментации рынка.

Правила:
- Отвечай ТОЛЬКО валидным JSON, без markdown-обёрток и пояснений.
- Если данные отсутствуют — используй null или пустой массив, не выдумывай.
- Все строки — на русском языке (если Brief на русском), иначе — на языке Brief.
- Не добавляй поля, которых нет в схеме.
- Будь конкретным и обоснованным."""
