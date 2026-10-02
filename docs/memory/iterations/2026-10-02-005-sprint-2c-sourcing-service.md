# Iteration 005 — Спринт 2C: sourcing-service

Date: 2026-10-02
Commit: (pending)

## Goal

Оркестратор OSINT: ICP-сегмент → коннекторы → нормализация (LLM) → скоринг → запись в contact-store.

## Changes (2C.1 + 2C.2 + 2C.3 закрыты)

- `services/sourcing-service/`: connectors (base/registry/serper/yandex/website_parser/registry_connector/enricher),
  llm (client/schemas/prompts), normalization, scoring (features/scorer), clients (icp/contact_store),
  service (orchestrator), repository, schemas, events, api.
- Таблицы `search_jobs`, `search_job_items` + RLS/FORCE.
- Endpoints: POST/GET /searches, /searches/stats, /searches/{id}, /searches/{id}/cancel, /searches/{id}/retry-failed.
- Компоуз (порт 48105), migrate.sh, healthcheck, CI.
- dev-console: вкладка «Поиски».

## Key fixes

- Гонка: фоновый job стартовал до коммита транзакции -> `search_job_not_found`. Решение: создавать job в
  отдельной сессии и коммитить ДО запуска asyncio-таски.
- `dict` без type-args -> mypy strict (массовый фикс).
- `enricher` возвращал Any -> fixed.

## Tests

- unit: serper, yandex, normalizer, scorer, website_parser, registry, enricher (25 тестов sourcing).
- integration: healthz, create+wait job, RLS.
- E2E вручную: сайт дистрибьютора -> raw 2 -> normalized 1 -> persisted 1 -> company в contact-store.
- События NATS: contacts.search_started / contacts.found.
- ruff, mypy strict (170 файлов), pytest — зелёные.

## Notes / next

- См. STATE.md. Далее — Спринт 3 (composer + review-queue).
- Ограничения dev (нет внешних ключей, память впритык) — в BACKLOG.md.
