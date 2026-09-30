# Iteration 001 — Memory layer + pricing + переход на deepseek-flash + Langfuse

Date: 2026-09-30
Commit: (pending)

## Goal

1. Построить memory layer для stateless-агента (`AGENTS.md` + `docs/memory/*`).
2. Вынести цены LLM и веса скоринга в справочники (`docs/reference/*`).
3. Перейти на модель `deepseek-flash` по умолчанию, удалить устаревшие `deepseek-chat`/`deepseek-reasoner`.
4. Подключить Langfuse.

## Changes

- `AGENTS.md` — точка входа для агента (порядок чтения, чеклист конца итерации).
- `docs/memory/PROJECT.md`, `STATE.md`, `DECISIONS.md` (ADR-001..011), `CONVENTIONS.md`, `GLOSSARY.md`, `BACKLOG.md`.
- `docs/reference/pricing.md` — цены `deepseek-flash` (peak/off-peak, cache hit/miss) и формула расчёта.
- `docs/reference/scoring.md` — все веса и алгоритм completeness/missing-info.
- `services/llm-gateway/src/llm_gateway/pricing.py` — единый слой цен.
- провайдер `deepseek.py` — модель `deepseek-flash`, учёт cache hit/miss.
- `langfuse_client.py` — реальная отправка трейсов.
- `.env` / `.env.example` — `deepseek-flash`, ключи DeepSeek и Langfuse.
- `docs/reference/langfuse.md` — инструкция по Langfuse и проверке трейсов.
- Langfuse подключён и проверен: трейсы доходят, model/usage/cost совпадают.

## Tests

- `uv run ruff check .` — green.
- `uv run mypy libs services` — green.
- `uv run pytest -q` — unit green.
- E2E бриф-цикла — green (см. STATE.md). Реальный LLM: intake → структурирование (completeness 0.69) → уточняющие вопросы → ответы. 7/7 интеграционных тестов на `deepseek-flash`.
- Найдено и исправлено: LLM присылает `null` для строковых/списочных полей → падало 500. Добавлена null-tolerant схема (`LLMSchemaBase`).

## Notes / next

- См. `STATE.md`, разделы «В работе» и «Далее».
