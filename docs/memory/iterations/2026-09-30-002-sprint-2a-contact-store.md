# Iteration 002 — Спринт 2A: contact-store

Date: 2026-09-30
Commit: (pending)

## Goal

Единый источник правды по компаниям и контактам: CRUD + upsert, детерминированный дедуп,
слияние дубликатов, stop-list, события.

## Changes

- `services/contact-store/` — новый сервис (models, normalization, fingerprint, merger, stoplist, repository, service, api).
- `libs/nats-client`: события `company.*`/`contact.*`, стрим `CONTACTS`.
- `libs/contracts/events.py`: payload-модели для company/contact событий.
- `infra/nats/nats-server.conf`: лимиты JetStream (8GB file store), проброшены в compose.
- `infra/docker-compose.dev.yml`: сервис contact-store (порт 48103).
- `scripts/migrate.sh`, `scripts/healthcheck.sh`, `.github/workflows/ci.yml`: добавлен contact-store.
- `docs/tasks/sprint-2a/`: 7 задач + overview.

## Key fixes

- `StopListEntry.tenant_id` — nullable (глобальные записи), объявлен вручную без TenantMixin.
- unique-индекс stoplist через COALESCE(NULL) — Postgres игнорирует NULL в уникальных индексах.
- NATS: ошибка insufficient storage resources available при создании стрима CONTACTS. Причина: JetStream бронирует место по сумме max_bytes стримов (~1.6 GiB), а дефолтный общий пул был ~1.2 GiB; фактических данных при этом < 1 MiB (проблема конфигурации, не объёма). Флагов --js-max-file-store у nats-server нет - вынес infra/nats/nats-server.conf с max_file_store 8GB, пробросил через command: -c. См. ADR-012.
- `company_id` из payload приходит строкой → приводим к UUID.
- RLS-политики null-safe (`NULLIF(current_setting(...), '')::uuid`) и FORCE на всех таблицах.

## Tests

- unit: normalization, fingerprint, merger (41 тест).
- integration: 6 тестов (company upsert/merge, contact + count, stoplist block, unsubscribe, RLS).
- `ruff`, `mypy --strict`, `pytest` — зелёные.
- E2E вручную: created→merged, bulk 5, unsubscribe→stoplist, RLS 404, события в NATS.

## Notes / next

- См. `STATE.md`. Далее — Спринт 2B (`icp-service`).
