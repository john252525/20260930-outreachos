# Outreach OS

Мульти-тенантная API-first платформа для целевого outreach: intake → ICP → OSINT-сорсинг →
генерация → ревью → отправка → аналитика. Собрана из автономных микросервисов (HTTP + NATS).

## Документация

- **Начни отсюда:** [`AGENTS.md`](AGENTS.md), [`docs/memory/PROJECT.md`](docs/memory/PROJECT.md), [`docs/memory/STATE.md`](docs/memory/STATE.md)
- Архитектура: [`docs/architecture.md`](docs/architecture.md) · Контракты: [`docs/contracts.md`](docs/contracts.md) · Инфра: [`docs/infra.md`](docs/infra.md)
- Справочники: [цены LLM](docs/reference/pricing.md) · [скоринг брифа](docs/reference/scoring.md) · [Langfuse](docs/reference/langfuse.md)
- Задачи: [Sprint 0](docs/tasks/sprint-0/) · [1](docs/tasks/sprint-1/) · [2A](docs/tasks/sprint-2a/) · [2B](docs/tasks/sprint-2b/) · [2C](docs/tasks/sprint-2c/) · [3A](docs/tasks/sprint-3a/) · [3B](docs/tasks/sprint-3b/) · [3C](docs/tasks/sprint-3c/)

## Статус

**Спринты 0–6 + UI «Проекты» (7-0) закрыты.** Платформа — самоуправляемый продукт с Web UI:
Brief → ICP → Sourcing → Composer → Review → Sender (email + Telegram + LinkedIn, dry-run) →
Reply-classifier → Analytics → A/B → auto-revision. Orchestrator связывает шаги; per-tenant settings.
Следующий — Спринт 7 (WhatsApp, bandit, ML-скоринг, users+roles, audit log).
Актуальный статус — в [`docs/memory/STATE.md`](docs/memory/STATE.md).

Сервисы: `tenant-service`, `llm-gateway`, `brief-service`, `contact-store`, `icp-service`,
`sourcing-service`, `composer-service`, `review-queue`, `sender-email`, `dev-console`.

## Быстрый старт

    cp .env.example .env   # заполнить секреты
    bash scripts/bootstrap.sh
    bash scripts/healthcheck.sh

Dev-console (инспектор): `http://<host>:48110/`

## Разработка

    export PATH="$PWD/.tools:$PATH"   # локальный uv
    uv sync --all-packages --all-groups
    uv run ruff check .
    uv run mypy libs services
    uv run pytest                      # unit-тесты
    uv run pytest -m integration       # интеграционные (нужен запущенный стек)

## Проверка после запуска (пример полного цикла)

    # 1. тенант
    T=$(curl -s -X POST http://127.0.0.1:48100/tenants -H "Content-Type: application/json" \
        -d '{"name":"Demo","slug":"demo"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

    # 2. бриф -> ICP -> запуск поиска -> черновик -> ревью -> отправка
    # см. docs/memory/STATE.md (карта портов) и эндпоинты в /docs каждого сервиса
