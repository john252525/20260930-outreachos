"""Base prompt primitives."""

from dataclasses import dataclass

PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM_COMMON = """Ты — ассистент, который помогает структурировать информацию о B2B-проектах для
последующего outreach.
Правила:
- Отвечай ТОЛЬКО валидным JSON, без markdown-обёрток и пояснений.
- Если данные отсутствуют — используй null, не выдумывай.
- Все строки — на русском языке (если исходные данные на русском), иначе — на языке исходных данных.
- Не добавляй поля, которых нет в схеме.
- Будь кратким и конкретным."""
