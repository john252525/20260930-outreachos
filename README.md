# Outreach OS

Мульти-тенантная API-first платформа для целевого outreach (intake → ICP → OSINT-сорсинг → генерация → ревью → отправка → аналитика).

## Документация

- [Архитектура](docs/architecture.md)
- [Контракты](docs/contracts.md)
- [Инфраструктура](docs/infra.md)
- [Память агента](docs/memory/PROJECT.md)
- [Цены LLM](docs/reference/pricing.md) · [Скоринг брифа](docs/reference/scoring.md) · [Langfuse](docs/reference/langfuse.md)
- [Задачи Спринта 0](docs/tasks/sprint-0/) · [Спринта 1](docs/tasks/sprint-1/)

## Статус

**Спринт 0 закрыт:** инфра (Postgres / NATS JetStream / Redis), библиотеки `common` / `contracts` / `db` / `nats-client` / `llm-client`, сервисы `tenant-service` и `llm-gateway`.

**Спринт 1 закрыт:** добавлен `brief-service` — адаптивный intake (сырой ввод → структурированный Brief v1 → уточняющие вопросы через LLM). Проверено: intake, ответы на вопросы, смена статусов (complete/abandon/reset/archive), события `brief.created/questions_asked/updated/completed`, RLS, идемпотентность, учёт LLM-вызовов.

## Быстрый старт

    cp .env.example .env   # заполнить секреты
    bash scripts/bootstrap.sh
    bash scripts/healthcheck.sh

## Разработка

    export PATH="$PWD/.tools:$PATH"   # локальный uv
    uv sync --all-packages --all-groups
    uv run ruff check .
    uv run mypy libs services
    uv run pytest

## Проверка после запуска

    # создать тенанта
    curl -X POST http://127.0.0.1:48100/tenants \
      -H "Content-Type: application/json" -H "Idempotency-Key: demo-1" \
      -d '{"name":"Demo","slug":"demo"}'

    # создать бриф
    curl -X POST http://127.0.0.1:48102/briefs \
      -H "Content-Type: application/json" -H "X-Tenant-ID: <tenant-id>" \
      -d '{"text":"Гидроборты для грузовиков, ищем дистрибьюторов"}'

    # вызвать LLM-шлюз (dev: провайдер mock)
    curl -X POST http://127.0.0.1:48101/v1/complete \
      -H "Content-Type: application/json" -H "X-Tenant-ID: <tenant-id>" \
      -d '{"task_type":"smoke","user":"привет","model":"mock"}'
