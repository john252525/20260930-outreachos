# PROJECT.md — Outreach OS

> Медленная память. Меняется редко, читается всегда.
> Актуальный статус сервисов — в `STATE.md`.

## Что это

**Outreach OS** — мульти-тенантная API-first платформа для целевого (прицельного) outreach:
от приёма вводных по проекту до отправки персонализированных писем и анализа отклика.

## Полный пайплайн (как связаны сервисы)

    intake        brief-service      сырой ввод -> Brief (LLM задаёт уточняющие вопросы)
                       |  brief.completed
    таргетинг     icp-service        Brief -> ICP + сегменты (LLM, веса скоринга)
                       |  icp.generated
    OSINT         sourcing-service   ICP-сегмент -> коннекторы -> нормализация (LLM) -> скоринг
                       |  contacts.found       (пишет в contact-store)
                       v
                  contact-store      единый источник правды: Company + Contact (+ stop-list)
                       |
    генерация     composer-service   Contact+Company+Brief+ICP -> черновик Message (LLM + шаблон + fact-check)
                       |  message.drafted
    ревью         review-queue       очередь human-in-the-loop: approve / reject / edit
                       |  message.approved
    отправка      sender-email       SMTP + ramp-up + stop-list + List-Unsubscribe -> message.sent
                       |
    аналитика     reply-classifier     reply.received -> классификация -> reply.classified
                       |  reply.classified
                  analytics-service    метрики (MV), funnel, reply rate, alerts
                  experiments-service  A/B (assign_variant), experiment.variant_won
    оркестрация   orchestrator         слушает события -> запускает следующие шаги (flows)
    авто-ревизия  auto-revision        analytics.alert -> диагноз (LLM) -> revision -> override+эксперимент
    каналы        sender-email (SMTP)  message.approved (email) -> message.sent
                  telegram-sender     message.approved (telegram) -> message.sent
                  linkedin-sender     message.approved (linkedin) -> message.sent (риск!)

Плюс `tenant-service` (проекты/тенанты) и `llm-gateway` (единая точка LLM) — инфраструктурные, используются всеми.

## Стек

- **Python 3.12 + FastAPI**, Pydantic v2, SQLAlchemy 2.0 (async) + Alembic, asyncpg.
- **uv** — пакетный менеджер и workspaces (монорепа, один `uv.lock`).
- **Postgres 16** — основная БД, мульти-тенантность через `tenant_id` + Row-Level Security.
- **NATS JetStream** — событийная шина (стримы `TENANTS`, `BRIEFS`, `CONTACTS`, `LLM_CALLS`, `SYSTEM`).
- **Redis** — кэш (LLM-ответы), идемпотентность (`Idempotency-Key`), rate-limit, ramp-up счётчики.
- **Docker Compose** — деплой (dev/stage/prod раздельно). Reverse-proxy — Caddy.
- **DeepSeek API** — LLM-провайдер (`deepseek-flash`), только через `llm-gateway`.
- **Langfuse** (cloud) — трейсинг LLM-вызовов.

## Структура репо

    libs/            common, contracts, db, nats-client, llm-client
    services/        tenant-service, llm-gateway, brief-service, contact-store, icp-service,
                     sourcing-service, composer-service, review-queue, sender-email,
                     reply-classifier, analytics-service, experiments-service,
                     orchestrator, auto-revision, telegram-sender, linkedin-sender, dev-console
apps/            web (Next.js UI + BFF proxy)
    infra/           docker-compose.dev.yml, postgres/init, nats/nats-server.conf
    scripts/         bootstrap, migrate, healthcheck, nats-cli, psql, redis-cli, logs, rebuild
    docs/            memory/, reference/, tasks/sprint-*/, architecture.md, contracts.md, infra.md

- Внутренние зависимости резолвятся через `[tool.uv.sources]` (workspace = true).
- Каждый сервис — свой Docker-образ (multi-stage, uv, non-root).
- `libs/contracts` — Pydantic-модели контрактов (Brief/ICP/Company/Contact/Message/Reply/Experiment +
  события). Версионируются, `extra="ignore"`.

## Память и справочники

- `docs/memory/` — память агента (PROJECT, STATE, DECISIONS, CONVENTIONS, GLOSSARY, BACKLOG, iterations/).
- `docs/reference/pricing.md` — LLM-цены и расчёт стоимости.
- `docs/reference/scoring.md` — completeness-скоринг брифа (веса, алгоритм).
- `docs/reference/langfuse.md` — LLM-трейсинг и как проверять вызовы.
- `docs/tasks/sprint-*/` — задачи по спринтам.
- `docs/contracts.md`, `docs/infra.md`, `docs/architecture.md` — исходные спеки Спринта 0.

## Внешние интеграции

| Сервис | Назначение | Конфиг | Статус (dev) |
|---|---|---|---|
| DeepSeek API | LLM (`deepseek-flash`) | `DEEPSEEK_API_KEY` | ключ есть |
| Langfuse Cloud | LLM-трейсинг | `LANGFUSE_PUBLIC_KEY/SECRET_KEY/BASE_URL` | ключи есть |
| Serper | веб-поиск (OSINT) | `SERPER_API_KEY` | пусто |
| Yandex XML | веб-поиск (OSINT) | `YANDEX_XML_USER/KEY` | пусто |
| DaData | реестр РФ (OSINT) | `DADATA_API_KEY/SECRET_KEY` | пусто |
| Hunter | enrichment email | `HUNTER_API_KEY` | пусто |
| SMTP/IMAP | отправка/приём email | `SENDER_ENCRYPTION_KEY`, `SENDER_DRY_RUN` | dry-run |

## Среда

- Деплой на VPS, docker-compose. Все наружу-торчащие порты сервисов — рандомные (карта в `STATE.md`).
- Postgres/NATS/Redis слушают только `127.0.0.1`.
- **Ограничение:** сервер делится с чужими проектами; память/диск часто «впритык». Свои сервисы — в
  контейнерах с префиксом `outreach-os-`.
