# PROJECT.md — Outreach OS

> Медленная память. Меняется редко, читается всегда.

## Что это

**Outreach OS** — мульти-тенантная API-first платформа для целевого (прицельного) outreach:
от приёма вводных по проекту до отправки персонализированных писем/сообщений и анализа отклика.

Целевой сценарий: у пользователя много ниш/проектов (от IT до промышленного производства).
По каждому проекту система:
1. принимает сырые вводные (текст, ссылку, ответы на вопросы),
2. строит структурированный **Brief**, дозадавая уточняющие вопросы через LLM,
3. строит **ICP** (профиль идеального клиента) и сегментирует,
4. ищет (OSINT) конкретные компании и контакты,
5. генерирует сообщения, даёт человеку проверить и отправить,
6. собирает обратную связь и считает метрики (A/B).

## Стек

- **Python 3.12 + FastAPI**, Pydantic v2, SQLAlchemy 2.0 (async) + Alembic, asyncpg.
- **uv** — пакетный менеджер и workspaces (монорепа).
- **Postgres 16** — основная БД, мульти-тенантность через `tenant_id` + RLS.
- **NATS JetStream** — событийная шина.
- **Redis** — кэш (LLM-ответы), идемпотентность (Idempotency-Key), rate-limit.
- **Docker Compose** — деплой (dev/stage/prod раздельно). Reverse-proxy — Caddy (на dev уже стоит).
- **DeepSeek API** — LLM-провайдер (модель `deepseek-flash`).
- **Langfuse** (cloud) — трейсинг LLM-вызовов (промпты/ответы/латентность/стоимость).

## Архитектура (микросервисы, API-first)

```
[HTTP / NATS] ──> [API/Core] ──> [Postgres + RLS]
                      │
                      ├──> [llm-gateway]        — единая точка выхода в LLM
                      ├──> [brief-service]      — intake → Brief v1
                      ├──> [icp-service]        — (Спринт 2)
                      ├──> [sourcing-service]   — (Спринт 2)
                      ├──> [contact-store]      — (Спринт 2)
                      ├──> [composer-service]   — (Спринт 3)
                      ├──> [review-queue]       — (Спринт 3)
                      ├──> [sender-email]       — (Спринт 4)
                      ├──> [reply-classifier]   — (Спринт 4)
                      ├──> [analytics-service]  — (Спринт 4)
                      └──> [cost-tracker]       — (Спринт 5)
```

Статус сервисов — в `STATE.md`.

## Структура репо

```
libs/            common, contracts, db, nats-client, llm-client
services/        tenant-service, llm-gateway, brief-service, ...
infra/           docker-compose.dev.yml, postgres/init, nats
scripts/         bootstrap, migrate, healthcheck, nats-cli, psql, ...
docs/            memory/, reference/, tasks/sprint-*/, architecture.md, contracts.md, infra.md
```

- Внутренние зависимости резолвятся через `[tool.uv.sources]` (workspace = true).
- Каждый сервис — свой Docker-образ (multi-stage, uv, non-root).
- `libs/contracts` — Pydantic-модели контрактов (Brief/ICP/Contact/.../события).

## Память и справочники

- `docs/memory/` — память агента (PROJECT, STATE, DECISIONS, CONVENTIONS, GLOSSARY, BACKLOG, iterations/).
- `docs/reference/pricing.md` — LLM-цены и расчёт стоимости.
- `docs/reference/scoring.md` — completeness-скоринг брифа.
- `docs/contracts.md`, `docs/infra.md`, `docs/architecture.md` — исходные спеки Спринта 0.

## Внешние интеграции

| Сервис | Назначение | Конфиг |
|---|---|---|
| DeepSeek API | LLM (`deepseek-flash`) | `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` |
| Langfuse Cloud | LLM-трейсинг | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` |
| Yandex/Serper/Brave | поиск для OSINT (Спринт 2) | — |
| SMTP/IMAP | отправка email (Спринт 4) | — |

## Среда

- Деплой на VPS, docker-compose. Все наружу-торчащие порты сервисов — рандомные (карта портов в `STATE.md`).
- Postgres/NATS/Redis слушают только `127.0.0.1`.
