# Outreach OS — Architecture

Мульти-тенантная API-first платформа для целевого outreach. Состоит из
автономных микросервисов, общающихся через HTTP (синхронно) и NATS JetStream
(асинхронно).

## Принципы

1. **API-first** — у каждого сервиса OpenAPI на `/docs`, версия, аутентификация
   по service-token + `X-Tenant-ID`.
2. **Мульти-тенантность с первого дня** — `tenant_id` в каждой таблице +
   Row-Level Security в Postgres (через непривилегированную роль `outreach_app`,
   `FORCE ROW LEVEL SECURITY`).
3. **Асинхронность по умолчанию** — события в NATS JetStream; синхронно только
   там, где нужен немедленный ответ.
4. **Stateless-сервисы** — состояние в Postgres/Redis/объектном хранилище.
5. **Идемпотентность** — заголовок `Idempotency-Key` на мутирующих запросах.
6. **Единый LLM-шлюз** — все вызовы LLM идут через `llm-gateway`.
7. **Evidence-принцип** — каждое фактическое утверждение имеет источник.

## Карта сервисов

| Сервис | Спринт | Назначение |
|---|---|---|
| `tenant-service` | 0 ✅ | CRUD проектов/тенантов, архивация |
| `llm-gateway` | 0 ✅ | Единая точка выхода в LLM, учёт токенов, кэш |
| `brief-service` | 1 ✅ | Приём вводных, уточняющие вопросы, Brief v1 |
| `icp-service` | 2B ✅ | Построение ICP/сегментов |
| `sourcing-service` | 2C ✅ | OSINT-поиск компаний и контактов |
| `contact-store` | 2A ✅ | Единая база компаний/контактов |
| `composer-service` | 3 | Генерация сообщений |
| `review-queue` | 3 | Human-in-the-loop очередь |
| `sender-email` | 4 | Отправка email с rate-limit и ramp-up |
| `reply-classifier` | 4 | Классификация входящих |
| `analytics-service` | 4 | Метрики, A/B |
| `cost-tracker` | 5 | Учёт расходов |

## События (NATS subjects)

`<domain>.<action>.<tenant_id>`, например `tenant.created.<uuid>`.

Стримы JetStream (создаются сервисами автоматически при старте):

| Stream | Subjects | Retention |
|---|---|---|
| `TENANTS` | `tenant.>` | limits, 365d |
| `BRIEFS` | `brief.>`, `icp.>`, `contacts.>`, `message.>`, `reply.>`, `experiment.>` | limits, 365d |
| `LLM_CALLS` | `llm.>`, `cost.>` | limits, 7d |
| `SYSTEM` | `system.>` | workqueue, 7d |

Публикация — лишь после успешного коммита транзакции. Дедупликация — через
`Nats-Msg-Id` (event_id).

## Контракты

Описаны в `docs/contracts.md` (Brief v1, ICP v1, Company/Contact v1,
Message/Reply v1, Experiment v1, события). Реализация — `libs/contracts`
(Pydantic v2, `extra="ignore"` для forward compatibility, UUID v7,
timezone-aware UTC).

## Хранилище

- **Postgres 16** — основная БД. `tenant_id` + RLS на каждой бизнес-таблице.
- **Redis** — кэш LLM-ответов, идемпотентность, rate-limit.
- **NATS JetStream** — событийная шина.
- (опционально) **MinIO/S3** — вложения и снапшоты.

## Пакетная структура (monorepo, uv workspaces)

# === Блок 2 ===
cd /opt/20260930-outreachos
cp .env.example .env    # заполнить секреты
bash scripts/bootstrap.sh

# === Блок 3 ===
bash scripts/logs.sh tenant-service     # логи сервиса
bash scripts/rebuild.sh llm-gateway     # пересборка одного сервиса
bash scripts/migrate.sh                 # применить миграции
bash scripts/healthcheck.sh             # проверить все сервисы
bash scripts/psql.sh                    # psql в Postgres
bash scripts/redis-cli.sh               # redis-cli
bash scripts/nats-cli.sh stream ls      # NATS CLI

# === Блок 4 ===
docker exec -T outreach-os-postgres pg_dump -U outreach -Fc outreach > backup-$(date +%F).dump

# === Блок 5 ===
cp .env.example .env   # заполнить секреты
bash scripts/bootstrap.sh
bash scripts/healthcheck.sh

# === Блок 6 ===
export PATH="$PWD/.tools:$PATH"   # локальный uv
uv sync --all-packages --all-groups
uv run ruff check .
uv run mypy libs services
uv run pytest

# === Блок 7 ===
# создать тенанта
curl -X POST http://127.0.0.1:48100/tenants \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-1" \
  -d '{"name":"Demo","slug":"demo"}'

# вызвать LLM-шлюз (dev: провайдер mock)
curl -X POST http://127.0.0.1:48101/v1/complete \
  -H "Content-Type: application/json" -H "X-Tenant-ID: <tenant-id>" \
  -d '{"task_type":"smoke","user":"привет","model":"mock"}'
