# Спринт 5 — Orchestrator + Auto-revision + Telegram sender

Проверил: зависимости от Спринта 0–4 соблюдены, порядок задач логичен, acceptance criteria проверяемы, нет противоречий с `docs/contracts.md`. Учёл, что Спринт 5 — **замыкает систему в самоуправляемый продукт**. До сих пор все шаги запускались вручную или полу-вручную. Спринт 5 делает их автоматическими и добавляет второй канал (Telegram).

## Что даёт Спринт 5

1. **Orchestrator.** Единый сервис, который подписывается на события и запускает следующие шаги. `brief.completed` → автоматически генерирует ICP. `icp.generated` → автоматически запускает sourcing. `contacts.found` → готовит черновики писем. Это превращает платформу из «набора микросервисов» в **продукт**.
2. **Auto-revision.** Если метрики ниже порога (например, reply rate < 2% на выборке ≥ 200), система сама предлагает переписать оффер. Через LLM анализирует, что не работает, генерирует новую версию шаблона, создаёт эксперимент.
3. **Telegram sender.** Второй канал. User-аккаунт через MTProto (Telethon) или бот. Важно: **не для холодного массового outreach**, а для тех, с кем уже есть контакт (например, после reply на email, или для тех, у кого есть публичный TG).
4. **WhatsApp sender.** Аналогично Telegram, через Business API или user-аккаунт. Отложим на Спринт 5B, если Telegram заработает.

## Разбивка на под-спринты

**5A — orchestrator.** Центральный сервис, который связывает всё через события. Это самое важное в Спринте 5.

**5B — auto-revision.** LLM-анализ метрик + генерация новых вариантов + авто-создание экспериментов.

**5C — Telegram sender.** Второй канал отправки.

**5D — WhatsApp sender (опционально).** Если Telegram заработает и будет время/необходимость.

**Порядок:** 5A → 5B → 5C → (5D). Orchestrator — фундамент, без него auto-revision не сможет запускать новые эксперименты, а Telegram sender не сможет получать сообщения из очереди.

**Что НЕ в этом спринте:**
- LinkedIn — отдельный спринт 6 (рискованный, банит).
- Мульти-armed bandit — отдельный спринт 6+.
- ML-модели для скоринга контактов (какой контакт с большей вероятностью ответит) — спринт 6+.
- Мультиязычность промптов за пределами RU/EN — спринт 6+.
- Multi-region deploy — отдельная инфраструктурная задача.

---

# 5A — `orchestrator`

## Что такое orchestrator и почему он важен

Это **дирижёр**. Он не делает работу сам — он слушает события и запускает следующие шаги. Без него каждый переход в пайплайне требует ручного вызова API. С ним — платформа работает как единый организм.

**Ключевые принципы:**
1. **Event-driven.** Всё через NATS. Orchestrator подписывается на события, решает, что делать, и вызывает API соответствующих сервисов.
2. **Idempotent.** Если событие обработано дважды — не должно быть дублей. Idempotency-Key на каждый вызов.
3. **Stateful per-flow.** Orchestrator отслеживает состояние каждой «цепочки» (например, `brief_id → icp_id → search_id`). Хранит в отдельной таблице.
4. **Configurable.** Какие шаги автоматические, а какие — требуют ручного подтверждения. Настраивается per tenant.
5. **Observable.** Каждый шаг логируется. Метрики: сколько flows, где застревают, сколько времени на шаг.
6. **Error-resilient.** Если шаг упал — retry с backoff. Если 3 раза — alert, ручное вмешательство.

## Архитектура

```
                    ┌──────────────────────────────────────────┐
                    │              orchestrator                 │
                    │                                           │
   NATS events ────►│  EventRouter                              │
                    │       │                                   │
                    │       ├──► FlowStateStore (Postgres)      │
                    │       │                                   │
                    │       ├──► StepHandlers                   │
                    │       │       ├──► BriefCompletedHandler  │
                    │       │       ├──► ICPGeneratedHandler    │
                    │       │       ├──► ContactsFoundHandler   │
                    │       │       ├──► MessageDraftedHandler  │
                    │       │       ├──► MessageApprovedHandler │
                    │       │       ├──► MessageSentHandler     │
                    │       │       └──► ReplyReceivedHandler   │
                    │       │                                   │
                    │       ├──► ServiceClients                 │
                    │       │       ├──► ICPClient              │
                    │       │       ├──► SourcingClient         │
                    │       │       ├──► ComposerClient         │
                    │       │       └──► ReviewQueueClient      │
                    │       │                                   │
                    │       └──► Publisher (NATS)               │
                    │                                           │
                    │  Events:                                  │
                    │   - flow.started                          │
                    │   - flow.step_completed                   │
                    │   - flow.completed                        │
                    │   - flow.failed                           │
                    └──────────────────────────────────────────┘
                                      │
                                      ▼
                                   Postgres
                          (flows, flow_steps)
```

**Модель данных:**
- `flows` — цепочки (одна на brief или на пачку outreach).
- `flow_steps` — шаги внутри цепочки.

---

# Задача 5A.1 — Каркас `orchestrator` + модели Flow / FlowStep

**Файл:** `docs/tasks/sprint-5a/5a.1-bootstrap.md`

## Цель

Создать каркас сервиса, определить модели `Flow` и `FlowStep`, миграция с RLS. Подписаться на ключевые события (brief.completed, icp.generated, contacts.found и т.д.).

## Зависимости

Спринт 4 закрыт.

## Что создать

```
services/orchestrator/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_flows.py
├── src/orchestrator/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── events.py
│   ├── router.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── brief_completed.py
│   │   ├── icp_generated.py
│   │   ├── contacts_found.py
│   │   ├── message_drafted.py
│   │   ├── message_approved.py
│   │   ├── message_sent.py
│   │   ├── reply_received.py
│   │   └── analytics_alert.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── icp_client.py
│   │   ├── sourcing_client.py
│   │   ├── composer_client.py
│   │   ├── review_queue_client.py
│   │   └── contact_store_client.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "orchestrator"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "redis>=5.2",
    "httpx>=0.27",
    "structlog>=24.4",
    "tenacity>=9.0",
    "common",
    "contracts",
    "db",
    "nats-client",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/orchestrator"]
```

### `config.py`

```python
from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field("orchestrator", alias="SERVICE_NAME")

    # Service URLs
    icp_service_url: str = Field(..., alias="ICP_SERVICE_URL")
    sourcing_service_url: str = Field(..., alias="SOURCING_SERVICE_URL")
    composer_service_url: str = Field(..., alias="COMPOSER_SERVICE_URL")
    review_queue_url: str = Field(..., alias="REVIEW_QUEUE_URL")
    contact_store_url: str = Field(..., alias="CONTACT_STORE_URL")
    brief_service_url: str = Field(..., alias="BRIEF_SERVICE_URL")
    sender_email_url: str = Field(..., alias="SENDER_EMAIL_URL")

    # Flow automation levels
    # "auto" — orchestrator запускает без подтверждения
    # "manual" — ждёт ручного API-вызова
    auto_brief_to_icp: bool = Field(True, alias="ORCH_AUTO_BRIEF_TO_ICP")
    auto_icp_to_sourcing: bool = Field(True, alias="ORCH_AUTO_ICP_TO_SOURCING")
    auto_contacts_to_drafts: bool = Field(False, alias="ORCH_AUTO_CONTACTS_TO_DRAFTS")  # по умолчанию false — сначала проверить
    auto_drafts_to_review: bool = Field(True, alias="ORCH_AUTO_DRAFTS_TO_REVIEW")
    auto_approved_to_send: bool = Field(True, alias="ORCH_AUTO_APPROVED_TO_SEND")

    # Sourcing default params
    default_sources: list[str] = Field(default_factory=lambda: ["serper"], alias="ORCH_DEFAULT_SOURCES")
    default_limit_per_source: int = Field(50, alias="ORCH_DEFAULT_LIMIT_PER_SOURCE")

    # Draft default params
    default_max_contacts_per_flow: int = Field(100, alias="ORCH_DEFAULT_MAX_CONTACTS")
    default_channel: str = Field("email", alias="ORCH_DEFAULT_CHANNEL")

    # Retry
    max_step_retries: int = Field(3, alias="ORCH_MAX_STEP_RETRIES")
    retry_delay_seconds: int = Field(60, alias="ORCH_RETRY_DELAY")

    # NATS
    nats_durable_name: str = Field("orchestrator", alias="NATS_DURABLE_NAME")
```

**Важно:** `auto_contacts_to_drafts=False` по умолчанию. Это значит, что после sourcing orchestrator **ждёт ручного запуска** генерации писем. Можно изменить через env.

### `models.py`

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.mixins import (
    MetadataMixin,
    SchemaVersionMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Flow(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    """Цепочка автоматизации. Одна на brief (или на пачку outreach)."""

    __tablename__ = "flows"

    flow_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # "brief_to_outreach" | "reply_followup" | "experiment_rollout"

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending | running | paused | completed | failed | cancelled

    # Связи
    brief_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    icp_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    search_job_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    # Параметры
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {sources, limit_per_source, channel, experiment_id, template_id, sender_config}

    # Прогресс
    current_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Сводка
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["FlowStep"]] = relationship(back_populates="flow", cascade="all, delete-orphan")


class FlowStep(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Отдельный шаг в цепочке."""

    __tablename__ = "flow_steps"

    flow_id: Mapped[UUID] = mapped_column(ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True)

    step_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # "generate_icp" | "start_sourcing" | "draft_messages" | "send_approved" | ...

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending | running | completed | failed | skipped | retry_scheduled

    # Вход/выход
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Retry
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    flow: Mapped[Flow] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_flow_steps_flow_step", "flow_id", "step_name"),
        Index("ix_flow_steps_status_retry", "status", "next_retry_at"),
    )
```

**Важно:**
- `flows` — цепочки. `flow_steps` — шаги внутри.
- `params` — гибкая структура, настраивается при создании.
- `next_retry_at` — для retry-логики. Отдельный воркер обрабатывает.

### Миграция

По образцу. RLS на обеих таблицах.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  orchestrator:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/orchestrator/Dockerfile
    container_name: outreach-orchestrator
    environment:
      <<: *common-env
      SERVICE_NAME: orchestrator
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/12
      ICP_SERVICE_URL: http://icp-service:8000
      SOURCING_SERVICE_URL: http://sourcing-service:8000
      COMPOSER_SERVICE_URL: http://composer-service:8000
      REVIEW_QUEUE_URL: http://review-queue:8000
      CONTACT_STORE_URL: http://contact-store:8000
      BRIEF_SERVICE_URL: http://brief-service:8000
      SENDER_EMAIL_URL: http://sender-email:8000
      ORCH_AUTO_BRIEF_TO_ICP: "true"
      ORCH_AUTO_ICP_TO_SOURCING: "true"
      ORCH_AUTO_CONTACTS_TO_DRAFTS: "false"
      ORCH_AUTO_DRAFTS_TO_REVIEW: "true"
      ORCH_AUTO_APPROVED_TO_SEND: "true"
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
      icp-service:
        condition: service_started
      sourcing-service:
        condition: service_started
      composer-service:
        condition: service_started
      review-queue:
        condition: service_started
    labels:
      caddy: orchestrator.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
```

Обновить `scripts/migrate.sh`.

### Dockerfile

Скопировать из `brief-service/Dockerfile`, поменять `--package orchestrator` и `CMD`.

### `main.py`

По образцу. Подписка на события через `Subscriber`. Каждое событие → свой handler.

**Важно:** используем **один durable consumer** для всех событий или **несколько** — по одному на тип? 

**Решение:** один durable, фильтр `["brief.completed.*", "icp.generated.*", "contacts.found.*", ...]`. `EventRouter` диспатчит по `event_type`.

## Acceptance criteria

```bash
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm orchestrator alembic upgrade head
# Ожидание: Applying 0001_create_flows... OK

docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d orchestrator
# Ожидание: service_started

curl -fsS https://orchestrator.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

bash scripts/psql.sh -c "\d+ flows"
bash scripts/psql.sh -c "\d+ flow_steps"
# Ожидание: обе таблицы, RLS enabled

curl -fsS https://orchestrator.dev.aitler.ru/openapi.json | jq .info.title
# Ожидание: "Orchestrator"
```

## Подсказки

- **`flows.params`** — гибкий. Не выносить в колонки.
- **`flow_steps.next_retry_at`** — отдельный воркер обрабатывает retry. См. 5A.4.
- **Один durable consumer** — проще, чем много.
- **`auto_*` флаги** — на уровне сервиса, не per-flow. Per-tenant настройки — Спринт 6.

## Анти-паттерны

- ❌ Не делать `flows` и `flow_steps` в одной таблице — разные жизненные циклы.
- ❌ Не забывать RLS.
- ❌ Не хранить всё в `params` — связи (`icp_id`, `search_job_id`) выносить в колонки.

---

# Задача 5A.2 — EventRouter + базовые handlers

**Файл:** `docs/tasks/sprint-5a/5a.2-handlers.md`

## Цель

Реализовать `EventRouter`, который диспатчит события по handlers. Реализовать `BriefCompletedHandler` и `ICPGeneratedHandler` — первые два шага автоматизации.

## Зависимости

5A.1.

## Что создать

```
services/orchestrator/src/orchestrator/
├── router.py
├── handlers/
│   ├── base.py
│   ├── brief_completed.py
│   └── icp_generated.py

services/orchestrator/tests/
├── test_router.py
├── test_brief_completed_handler.py
└── test_icp_generated_handler.py
```

## Детали

### `handlers/base.py`

```python
from abc import ABC, abstractmethod
from uuid import UUID

from contracts.base import EventEnvelope


class StepHandler(ABC):
    """Базовый интерфейс обработчика события."""

    event_type: str
    step_name: str

    @abstractmethod
    async def handle(self, envelope: EventEnvelope) -> None:
        """Обрабатывает событие. Может создавать FlowStep и вызывать сервисы."""
        ...
```

### `router.py`

```python
import structlog

from contracts.base import EventEnvelope
from orchestrator.handlers.base import StepHandler


logger = structlog.get_logger()


class EventRouter:
    """Диспатчит события по handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[StepHandler]] = {}

    def register(self, handler: StepHandler) -> None:
        self._handlers.setdefault(handler.event_type, []).append(handler)

    async def route(self, envelope: EventEnvelope) -> None:
        """Вызывает все handlers для данного event_type."""
        handlers = self._handlers.get(envelope.event_type, [])
        if not handlers:
            logger.debug("no_handlers_for_event", event_type=envelope.event_type)
            return

        for h in handlers:
            try:
                await h.handle(envelope)
            except Exception as e:
                # Не пробрасываем — другие handlers должны выполниться
                logger.exception(
                    "handler_failed",
                    event_type=envelope.event_type,
                    handler=h.__class__.__name__,
                    error=str(e),
                )
```

### `handlers/brief_completed.py`

```python
from uuid import UUID

import structlog

from common.errors import AppError
from contracts.base import EventEnvelope
from orchestrator.clients.icp_client import ICPClient
from orchestrator.config import Settings
from orchestrator.events import emit_flow_started, emit_flow_failed
from orchestrator.handlers.base import StepHandler
from orchestrator.models import Flow, FlowStep
from orchestrator.repository import FlowRepository
from nats_client.publisher import Publisher


logger = structlog.get_logger()


class BriefCompletedHandler(StepHandler):
    event_type = "brief.completed"
    step_name = "generate_icp"

    def __init__(
        self,
        repo: FlowRepository,
        icp_client: ICPClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._icp = icp_client
        self._publisher = publisher
        self._settings = settings

    async def handle(self, envelope: EventEnvelope) -> None:
        if not self._settings.auto_brief_to_icp:
            logger.info("brief_to_icp_skipped_manual_mode", brief_id=envelope.payload.get("brief", {}).get("id"))
            return

        brief_id = envelope.payload["brief"]["id"]
        tenant_id = envelope.tenant_id

        # 1. Создаём Flow, если ещё нет для этого brief
        existing = await self._repo.find_by_brief(tenant_id, brief_id)
        if existing is not None:
            logger.info("flow_exists_for_brief", flow_id=str(existing.id), brief_id=brief_id)
            return

        flow = Flow(
            tenant_id=tenant_id,
            flow_type="brief_to_outreach",
            status="running",
            brief_id=brief_id,
            params={
                "sources": self._settings.default_sources,
                "limit_per_source": self._settings.default_limit_per_source,
                "channel": self._settings.default_channel,
                "auto_draft": self._settings.auto_contacts_to_drafts,
            },
            current_step="generate_icp",
            total_steps=4,  # generate_icp → start_sourcing → draft_messages → send_approved
            started_at=datetime.now(timezone.utc),
            trace_id=envelope.trace_id,
        )
        await self._repo.add_flow(flow)

        step = FlowStep(
            tenant_id=tenant_id,
            flow_id=flow.id,
            step_name=self.step_name,
            status="running",
            input_data={"brief_id": brief_id},
            started_at=datetime.now(timezone.utc),
            max_attempts=self._settings.max_step_retries,
        )
        await self._repo.add_step(step)

        await emit_flow_started(self._publisher, flow, trace_id=envelope.trace_id)

        # 2. Вызываем icp-service
        try:
            icp = await self._icp.generate_icp(
                tenant_id=str(tenant_id),
                brief_id=brief_id,
                trace_id=envelope.trace_id,
            )
            icp_id = icp["id"]

            # 3. Обновляем flow и step
            flow.icp_id = UUID(icp_id)
            flow.completed_steps = 1
            await self._repo._s.flush()

            step.status = "completed"
            step.output_data = {"icp_id": icp_id, "segments_count": icp.get("segments_count")}
            step.finished_at = datetime.now(timezone.utc)
            step.duration_ms = int((step.finished_at - step.started_at).total_seconds() * 1000)
            await self._repo._s.flush()

            logger.info("flow_step_completed", flow_id=str(flow.id), step=self.step_name, icp_id=icp_id)
        except Exception as e:
            logger.exception("brief_completed_handler_failed", brief_id=brief_id, error=str(e))
            step.status = "failed"
            step.error = str(e)
            step.attempts += 1
            step.finished_at = datetime.now(timezone.utc)
            if step.attempts >= step.max_attempts:
                flow.status = "failed"
                flow.error = f"Step {self.step_name} failed after {step.attempts} attempts"
                flow.finished_at = datetime.now(timezone.utc)
                await emit_flow_failed(self._publisher, flow, step, trace_id=envelope.trace_id)
            else:
                step.status = "retry_scheduled"
                step.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=self._settings.retry_delay_seconds)
            await self._repo._s.flush()
            raise
```

**Важно:**
- Handler создаёт Flow и FlowStep **до** вызова сервиса. Так мы видим прогресс даже при падении.
- При ошибке — retry через `next_retry_at`. Отдельный воркер (5A.4) обрабатывает.
- `emit_flow_started` / `emit_flow_failed` — события для observability.

### `handlers/icp_generated.py`

```python
class ICPGeneratedHandler(StepHandler):
    event_type = "icp.generated"
    step_name = "start_sourcing"

    def __init__(self, repo, sourcing_client, publisher, settings) -> None:
        ...

    async def handle(self, envelope: EventEnvelope) -> None:
        if not self._settings.auto_icp_to_sourcing:
            return

        icp_id = envelope.payload["icp"]["id"]
        tenant_id = envelope.tenant_id
        brief_id = envelope.payload["icp"]["brief_id"]

        # Находим flow по brief_id
        flow = await self._repo.find_by_brief(tenant_id, brief_id)
        if flow is None:
            logger.warning("flow_not_found_for_icp", icp_id=icp_id)
            return

        if flow.status != "running":
            return

        # Обновляем flow
        flow.icp_id = UUID(icp_id)
        flow.current_step = self.step_name
        await self._repo._s.flush()

        # Создаём step
        step = FlowStep(
            tenant_id=tenant_id,
            flow_id=flow.id,
            step_name=self.step_name,
            status="running",
            input_data={"icp_id": icp_id},
            started_at=datetime.now(timezone.utc),
            max_attempts=self._settings.max_step_retries,
        )
        await self._repo.add_step(step)

        # Получаем ICP, чтобы взять segment_id
        icp = await self._icp.get_icp(icp_id, tenant_id=str(tenant_id))
        segments = icp.get("payload", {}).get("segments", [])
        if not segments:
            step.status = "failed"
            step.error = "No segments in ICP"
            await self._repo._s.flush()
            return

        # Для каждого сегмента — отдельный search job
        search_job_ids = []
        for segment in segments[:self._settings.max_sources_per_search]:
            try:
                job = await self._sourcing.start_search(
                    tenant_id=str(tenant_id),
                    icp_id=icp_id,
                    segment_id=segment["id"],
                    sources=flow.params.get("sources"),
                    limit_per_source=flow.params.get("limit_per_source"),
                    trace_id=envelope.trace_id,
                )
                search_job_ids.append(job["id"])
            except Exception as e:
                logger.warning("sourcing_segment_failed", segment_id=segment["id"], error=str(e))

        step.status = "completed"
        step.output_data = {"search_job_ids": search_job_ids}
        step.finished_at = datetime.now(timezone.utc)
        flow.search_job_id = UUID(search_job_ids[0]) if search_job_ids else None
        flow.completed_steps += 1
        await self._repo._s.flush()

        logger.info("sourcing_started", flow_id=str(flow.id), jobs=len(search_job_ids))
```

**Важно:** для нескольких сегментов ICP запускаем несколько search jobs. Orchestrator ждёт событий `contacts.found` от каждого.

### `events.py`

```python
async def emit_flow_started(publisher, flow: Flow, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.FLOW_STARTED,
        tenant_id=flow.tenant_id,
        payload={"flow": {"id": str(flow.id), "type": flow.flow_type, "brief_id": flow.brief_id}},
        trace_id=trace_id,
        correlation_id=flow.id,
    )


async def emit_flow_step_completed(publisher, flow, step, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.FLOW_STEP_COMPLETED,
        tenant_id=flow.tenant_id,
        payload={
            "flow_id": str(flow.id),
            "step_name": step.step_name,
            "duration_ms": step.duration_ms,
        },
        trace_id=trace_id,
    )


async def emit_flow_completed(publisher, flow, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.FLOW_COMPLETED,
        tenant_id=flow.tenant_id,
        payload={"flow": {"id": str(flow.id), "type": flow.flow_type}},
        trace_id=trace_id,
    )


async def emit_flow_failed(publisher, flow, step, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.FLOW_FAILED,
        tenant_id=flow.tenant_id,
        payload={
            "flow_id": str(flow.id),
            "step_name": step.step_name,
            "error": step.error,
        },
        trace_id=trace_id,
    )
```

**Добавить в `nats_client.subjects`:** `FLOW_STARTED`, `FLOW_STEP_COMPLETED`, `FLOW_COMPLETED`, `FLOW_FAILED`. Стрим — `SYSTEM` (не бизнес-данные, короткий retention).

### `main.py`

```python
from orchestrator.router import EventRouter
from orchestrator.handlers.brief_completed import BriefCompletedHandler
from orchestrator.handlers.icp_generated import ICPGeneratedHandler

# в lifespan:
router = EventRouter()
router.register(BriefCompletedHandler(repo_factory, icp_client, publisher, settings))
router.register(ICPGeneratedHandler(repo_factory, sourcing_client, publisher, settings))
app.state.router = router

# подписка на события
async def _on_event(envelope) -> None:
    await router.route(envelope)

subscriber = Subscriber(
    nats_conn,
    stream="BRIEFS",
    durable=settings.nats_durable_name,
    filter_subjects=[
        "brief.completed.*",
        "icp.generated.*",
        "contacts.found.*",
        "message.drafted.*",
        "message.approved.*",
        "message.sent.*",
        "reply.received.*",
        "analytics.alert.*",
    ],
    handler=_on_event,
)
await subscriber.start()
asyncio.create_task(subscriber.run_forever())
```

**Важно:** `repo_factory` — потому что каждый handler в своём контексте БД. Используем `async_session_factory` + `set_tenant_context`. В `main.py` — обёртка.

**Проблема:** subscriber не знает tenant_id до получения envelope. Значит, session с RLS устанавливается **внутри handler'а**, после получения `tenant_id` из envelope.

**Решение:** handler получает `session_factory`, создаёт session сам, ставит RLS-контекст.

```python
# в handler:
async with async_session_factory() as session:
    async with session.begin():
        await set_tenant_context(session, envelope.tenant_id)
        repo = FlowRepository(session)
        ...
```

## Acceptance criteria

```bash
# 1. Создать и завершить brief
BRIEF_ID=$(curl -sX POST https://brief.dev.aitler.ru/briefs ... | jq -r .id)
# ... ответить на все вопросы до complete

# 2. Дождаться автоматической генерации ICP
sleep 10
curl -s -H "X-Tenant-ID: $TENANT" "https://orchestrator.dev.aitler.ru/flows?brief_id=$BRIEF_ID" | jq '.[0] | {id, status, current_step, icp_id, completed_steps, total_steps}'
# Ожидание: flow в статусе running/completed, icp_id заполнен

# 3. ICP создан автоматически
curl -s -H "X-Tenant-ID: $TENANT" "https://icp.dev.aitler.ru/icps?brief_id=$BRIEF_ID" | jq '.[0]'
# Ожидание: ICP существует

# 4. Sourcing запущен автоматически
sleep 30
curl -s -H "X-Tenant-ID: $TENANT" "https://orchestrator.dev.aitler.ru/flows?brief_id=$BRIEF_ID" | jq '.[0] | {status, search_job_id, completed_steps}'
# Ожидание: search_job_id заполнен, completed_steps >= 2

# 5. События
bash scripts/nats-cli.sh stream view SYSTEM --last 20 | grep -E "flow\.(started|step_completed|completed|failed)"
# Ожидание: есть
```

## Подсказки

- **Handler сам создаёт session** — потому что tenant_id известен только после получения envelope.
- **Flow создаётся в первом handler'е** (`brief_completed`). Остальные handlers находят его по `brief_id`.
- **Если flow не найден** — handler логирует и продолжает. Это может быть ручной вызов ICP без брифа.
- **`auto_brief_to_icp=False`** — handler ничего не делает. Это для ручного режима.

## Анти-паттерны

- ❌ Не создавать session до получения envelope.
- ❌ Не пробрасывать ошибку из handler'а в router — логируем и продолжаем.
- ❌ Не блокировать subscriber на долгих операциях — handler должен быть быстрым (< 30 сек). Долгие операции — через фоновые задачи.

---

# Задача 5A.3 — Остальные handlers + API

**Файл:** `docs/tasks/sprint-5a/5a.3-rest-handlers.md`

## Цель

Реализовать handlers для остальных событий: `contacts.found`, `message.drafted`, `message.approved`, `message.sent`, `reply.received`, `analytics.alert`. Плюс API для чтения flows и ручного управления.

## Детали

### `handlers/contacts_found.py`

Логика:
- Найти flow по `search_job_id`.
- Если `auto_draft=True` (из flow.params) — для каждого контакта создать draft через composer.
- Если `auto_draft=False` — обновить flow, ждать ручного запуска.

```python
class ContactsFoundHandler(StepHandler):
    event_type = "contacts.found"
    step_name = "draft_messages"

    async def handle(self, envelope: EventEnvelope) -> None:
        search_job_id = envelope.payload.get("search_job_id")  # или из job
        # ... найти flow
        flow = await self._repo.find_by_search_job(tenant_id, UUID(search_job_id))
        if flow is None:
            return

        # Обновляем step для sourcing как completed
        # ...

        if not flow.params.get("auto_draft"):
            logger.info("contacts_found_awaiting_manual_draft", flow_id=str(flow.id))
            flow.status = "paused"
            await self._repo._s.flush()
            return

        # Получаем контакты из contact-store (status=candidate, created этим search_job)
        # Создаём drafts через composer
        # Лимит: max_contacts_per_flow
        ...
```

**Важно:** для «какие контакты создал этот search_job» — нужен endpoint в contact-store: `GET /contacts?source_search_job_id=X`. Или используем `search_job_items` из sourcing-service.

**Решение:** добавить поле `source_search_job_id` в Contact (metadata) при persist в sourcing. Затем фильтр в contact-store по metadata.

**Или проще:** sourcing-service в событии `contacts.found` передаёт список `contact_ids` и `company_ids`. Orchestrator берёт их напрямую.

**Обновить sourcing `emit_contacts_found`:**

```python
await emit_contacts_found(
    self._publisher,
    job,
    count=persisted_count,
    company_ids=[str(i.company_id) for i in items if i.company_id],
    contact_ids=[cid for i in items for cid in (i.contact_ids or [])],  # NEW
    trace_id=trace_id,
)
```

Тогда orchestrator получает список напрямую.

### `handlers/message_drafted.py`

Ничего не делает, если `auto_drafts_to_review=True` — review-queue уже подписан. Логирует.

### `handlers/message_approved.py`

Ничего не делает — sender-email уже подписан. Логирует.

### `handlers/message_sent.py`

Обновляет flow: увеличивает `completed_steps` (для draft → send). Проверяет, завершён ли flow.

### `handlers/reply_received.py`

Логика:
- Найти flow по `message_id` → `contact_id` → flow.
- Если reply positive → flow завершён успешно.
- Если reply negative → flow завершён.
- Логирует, обновляет метрики.

### `handlers/analytics_alert.py`

Логика:
- Принимает alert.
- Если `low_reply_rate` — создаёт Flow `auto_revision` (см. 5B).
- Если `high_bounce_rate` — приостанавливает flow, алертит.

### API

```python
@router.get("/flows", response_model=list[FlowSummary])
async def list_flows(
    status_filter: str | None = Query(None, alias="status"),
    flow_type: str | None = Query(None),
    brief_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc=Depends(get_service),
) -> list[FlowSummary]:
    ...


@router.get("/flows/{flow_id}", response_model=FlowRead)
async def get_flow(flow_id: UUID, svc=Depends(get_service)) -> FlowRead:
    ...


@router.get("/flows/{flow_id}/steps", response_model=list[FlowStepRead])
async def get_flow_steps(flow_id: UUID, svc=Depends(get_service)) -> list[FlowStepRead]:
    ...


@router.post("/flows/{flow_id}/pause", response_model=FlowRead)
async def pause_flow(flow_id: UUID, svc=Depends(get_service)) -> FlowRead:
    """Приостанавливает flow — handlers не будут выполняться для него."""
    ...


@router.post("/flows/{flow_id}/resume", response_model=FlowRead)
async def resume_flow(flow_id: UUID, svc=Depends(get_service)) -> FlowRead:
    ...


@router.post("/flows/{flow_id}/cancel", response_model=FlowRead)
async def cancel_flow(flow_id: UUID, svc=Depends(get_service)) -> FlowRead:
    ...


@router.post("/flows/{flow_id}/trigger-draft", response_model=FlowRead)
async def trigger_draft(
    flow_id: UUID,
    data: TriggerDraftRequest,  # {contact_ids: list[UUID] | None, channel, template_id, sender_config}
    svc=Depends(get_service),
) -> FlowRead:
    """Ручной запуск генерации черновиков (когда auto_draft=False)."""
    ...


@router.get("/stats")
async def stats(svc=Depends(get_service)) -> dict:
    """Агрегаты по flows: сколько running, completed, failed, среднее время шага."""
    ...
```

### Методы сервиса

```python
class OrchestratorService:
    async def list_flows(self, *, tenant_id: UUID, **kwargs) -> list[Flow]: ...
    async def get_flow(self, flow_id: UUID) -> Flow: ...
    async def get_flow_steps(self, flow_id: UUID) -> list[FlowStep]: ...
    async def pause_flow(self, flow_id: UUID) -> Flow: ...
    async def resume_flow(self, flow_id: UUID) -> Flow: ...
    async def cancel_flow(self, flow_id: UUID) -> Flow: ...
    async def trigger_draft(self, *, tenant_id: UUID, flow_id: UUID, data: TriggerDraftRequest, trace_id: str) -> Flow:
        """Ручной запуск draft для контактов flow."""
        ...
```

**Важно:** handler'ы должны проверять `flow.status == "running"`. Если `paused` или `cancelled` — пропускать. Добавить проверку во все handlers.

## Acceptance criteria

```bash
# 1. Ручной trigger draft
curl -sX POST https://orchestrator.dev.aitler.ru/flows/$FLOW_ID/trigger-draft \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: td-1" \
  -d '{
    "channel": "email",
    "template_id": "email_cold_outreach",
    "sender_config": {"sender_from_name": "Сергей", "sender_from_email": "s@example.com", "sender_signature": "Сергей"}
  }' | jq '.status, .current_step'
# Ожидание: "running", "draft_messages"

# 2. Дождаться создания черновиков
sleep 60
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/messages?limit=10 | jq 'length'
# Ожидание: >= 1

# 3. Flow progress
curl -s -H "X-Tenant-ID: $TENANT" https://orchestrator.dev.aitler.ru/flows/$FLOW_ID | jq '{status, completed_steps, total_steps}'
# Ожидание: completed_steps >= 3

# 4. Stats
curl -s -H "X-Tenant-ID: $TENANT" https://orchestrator.dev.aitler.ru/stats | jq .
# Ожидание: агрегаты по flows
```

## Подсказки

- **Проверка `flow.status`** — во всех handlers. Если не running — пропускаем.
- **`trigger_draft`** — ручной запуск, когда auto_draft=False. Создаёт drafts для контактов flow.
- **`total_steps`** — обновляется по мере прохождения. Изначально 4.
- **При завершении flow** (`all steps completed`) — публикуем `flow.completed`.

## Анти-паттерны

- ❌ Не позволять handlers работать на paused/cancelled flows.
- ❌ Не забывать проверять `flow.status` в каждом handler.
- ❌ Не терять контакты при trigger_draft.

---

# Задача 5A.4 — Retry worker + observability

**Файл:** `docs/tasks/sprint-5a/5a.4-retry-observability.md`

## Цель

Фоновый воркер: обрабатывает `flow_steps` со статусом `retry_scheduled` и `next_retry_at <= now()`. Плюс метрики для observability.

## Детали

### Retry worker

```python
import asyncio
from datetime import datetime, timezone

import structlog

from orchestrator.config import Settings
from orchestrator.repository import FlowRepository
from db.session import async_session_factory
from db.rls import set_tenant_context


logger = structlog.get_logger()


class RetryWorker:
    """Обрабатывает retry для flow_steps."""

    def __init__(self, router, settings: Settings) -> None:
        self._router = router
        self._settings = settings
        self._stopped = False

    async def run_forever(self) -> None:
        while not self._stopped:
            try:
                await self._process_retries()
            except Exception as e:
                logger.exception("retry_worker_failed", error=str(e))
            await asyncio.sleep(30)

    async def _process_retries(self) -> None:
        # Получаем все tenant'ы (упрощённо)
        from sqlalchemy import select
        from orchestrator.models import Tenant  # НЕТ — тенантов в orchestrator нет
        # Читаем из public.tenants
        ...
        async with async_session_factory() as session:
            # Без tenant context — читаем все flow_steps через суперпользователя
            # Или через отдельную роль без RLS
            result = await session.execute(
                select(FlowStep)
                .where(
                    FlowStep.status == "retry_scheduled",
                    FlowStep.next_retry_at <= datetime.now(timezone.utc),
                )
                .limit(10)
            )
            steps = result.scalars().all()

        for step in steps:
            tenant_id = step.tenant_id
            try:
                # Перезапускаем handler через router с тем же событием
                # Проблема: нам нужно событие. Оно уже было обработано.
                # Решение: храним event_payload в step.input_data, переигрываем
                ...
            except Exception as e:
                logger.exception("retry_step_failed", step_id=str(step.id), error=str(e))
```

**Проблема:** retry требует повторного выполнения handler'а. Но handler вызывается с `EventEnvelope`, а не с FlowStep.

**Решение:** переделать handlers так, чтобы они могли вызываться **двумя способами**:
1. Из router'а (по событию).
2. Из retry worker'а (по FlowStep).

**Подход:** каждый handler имеет метод `handle(envelope)` и `handle_step(step)`. Общая логика — в `_execute(tenant_id, params, step)`.

**Или проще:** retry worker пересоздаёт event из step.input_data и публикует его заново в NATS. Тогда handler вызовется как обычно.

**Выбираем второе:** `step.input_data` хранит `{event_type, event_payload, original_envelope}`. Retry worker публикует событие заново. Но это создаст дубликат в NATS — нужно дедуп.

**Ещё проще:** retry worker делает прямой HTTP-вызов нужного сервиса, минуя событие. Для каждого `step_name` знает, какой client вызвать.

**Решение:** retry worker — простой. Он для каждого step:
1. Создаёт новый `EventEnvelope` с тем же payload.
2. Вызывает `router.route(envelope)` напрямую (не через NATS).

Это переиспользует handlers и не создаёт дублей в NATS.

```python
async def _process_retries(self) -> None:
    async with async_session_factory() as session:
        # Без RLS — используем роль без RLS-ограничений для cross-tenant чтения
        # Или: для каждого tenant отдельный запрос
        ...
        for step in steps:
            # Восстанавливаем envelope из step.input_data
            event_type = step.input_data.get("original_event_type")
            event_payload = step.input_data.get("original_event_payload")
            if not event_type or not event_payload:
                # Нет данных для retry — помечаем failed
                step.status = "failed"
                step.error = "No original event data for retry"
                continue

            envelope = EventEnvelope(
                event_id=uuid7(),
                event_type=event_type,
                schema_version="1.0",
                occurred_at=datetime.now(timezone.utc),
                tenant_id=step.tenant_id,
                trace_id=f"retry-{step.id}",
                producer="orchestrator/retry-worker",
                payload=event_payload,
            )
            step.status = "running"
            step.attempts += 1
            await session.flush()

            try:
                await self._router.route(envelope)
                step.status = "completed"
                step.finished_at = datetime.now(timezone.utc)
            except Exception as e:
                if step.attempts >= step.max_attempts:
                    step.status = "failed"
                    step.error = f"Retry failed after {step.attempts} attempts: {e}"
                else:
                    step.status = "retry_scheduled"
                    step.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=self._settings.retry_delay_seconds * (2 ** step.attempts))  # exponential backoff
            await session.flush()
```

**Важно:** `step.input_data` должен содержать `original_event_type` и `original_event_payload`. Обновить handlers — при создании step сохранять это.

**Обновить в каждом handler'е:**

```python
step = FlowStep(
    tenant_id=tenant_id,
    flow_id=flow.id,
    step_name=self.step_name,
    status="running",
    input_data={
        "brief_id": brief_id,
        "original_event_type": envelope.event_type,
        "original_event_payload": envelope.payload,
    },
    ...
)
```

### Observability

**Метрики (Prometheus):**
- `orchestrator_flows_total{status, flow_type}` — счётчик flows.
- `orchestrator_flow_steps_total{step_name, status}` — счётчик шагов.
- `orchestrator_flow_step_duration_seconds{step_name}` — гистограмма.
- `orchestrator_flow_step_retries_total{step_name}` — счётчик retry.

**Эндпоинт `/metrics`** — стандартный Prometheus. Использовать `prometheus-client`.

**Добавить `prometheus-client>=0.21` в зависимости.**

```python
# metrics.py
from prometheus_client import Counter, Histogram


FLOWS_TOTAL = Counter(
    "orchestrator_flows_total",
    "Total flows",
    ["status", "flow_type"],
)

FLOW_STEPS_TOTAL = Counter(
    "orchestrator_flow_steps_total",
    "Total flow steps",
    ["step_name", "status"],
)

FLOW_STEP_DURATION = Histogram(
    "orchestrator_flow_step_duration_seconds",
    "Flow step duration",
    ["step_name"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300, 900, 3600],
)

FLOW_STEP_RETRIES = Counter(
    "orchestrator_flow_step_retries_total",
    "Flow step retries",
    ["step_name"],
)
```

**Использование в handlers:** `FLOW_STEPS_TOTAL.labels(step_name=self.step_name, status="completed").inc()`.

**Эндпоинт `/metrics`** — добавить в `main.py`:

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### API для observability

```python
@router.get("/stats")
async def stats(svc=Depends(get_service)) -> dict:
    """Агрегаты по flows и шагам."""
    # SELECT status, flow_type, COUNT(*) FROM flows GROUP BY 1, 2
    # SELECT step_name, status, COUNT(*), AVG(duration_ms), SUM(attempts) FROM flow_steps GROUP BY 1, 2
    ...
```

## Acceptance criteria

```bash
# 1. Симулировать retry: сломать ICP-service на время
docker compose ... stop icp-service
# Создать brief и завершить
# ...
# Дождаться, что flow failed с retry_scheduled
curl -s -H "X-Tenant-ID: $TENANT" https://orchestrator.dev.aitler.ru/flows/$FLOW_ID | jq '.steps[] | {step_name, status, attempts, next_retry_at}'
# Ожидание: retry_scheduled

# 2. Запустить ICP-service обратно
docker compose ... start icp-service
# Через минуту retry worker должен выполнить шаг
sleep 90
curl -s -H "X-Tenant-ID: $TENANT" https://orchestrator.dev.aitler.ru/flows/$FLOW_ID | jq '.steps[] | {step_name, status, attempts}'
# Ожидание: completed

# 3. Метрики
curl -s https://orchestrator.dev.aitler.ru/metrics | grep orchestrator_
# Ожидание: метрики

# 4. Stats
curl -s -H "X-Tenant-ID: $TENANT" https://orchestrator.dev.aitler.ru/stats | jq .
# Ожидание: агрегаты
```

## Подсказки

- **Retry worker использует router напрямую** — не через NATS. Это переиспользует handlers.
- **`original_event_type` и `original_event_payload`** — обязательны в step.input_data.
- **Exponential backoff** — `delay * 2^attempts`.
- **`/metrics`** — стандартный Prometheus endpoint.

## Анти-паттерны

- ❌ Не публиковать событие заново в NATS — только прямой вызов router.
- ❌ Не делать retry бесконечным — `max_attempts`.
- ❌ Не забывать про exponential backoff.

---

# Задача 5A.5 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-5a/5a.5-tests.md`

## Цель

Покрытие 85%+, E2E полного flow «brief → ICP → sourcing → draft», обновить CI.

## Детали

### E2E

1. Создать brief.
2. Ответить на все вопросы (mock brief-service).
3. Дождаться автоматической генерации ICP (mock icp-service).
4. Дождаться автоматического sourcing (mock sourcing-service).
5. Ручной trigger-draft.
6. Проверить, что drafts созданы (mock composer).
7. Проверить события flow.*.

### CI

Добавить `orchestrator` в matrix.

## Acceptance criteria

```bash
uv run pytest services/orchestrator/tests/ -v --cov=orchestrator --cov-report=term-missing
# Ожидание: coverage >= 85%
```

---

# 5B — `auto-revision`

## Что такое auto-revision

Это **замыкание обратной связи**. Если outreach работает плохо (reply rate < threshold на достаточной выборке), система сама предлагает переписать оффер.

**Ключевые принципы:**
1. **Не автоматическая отправка.** Создаётся **предложение** — новый вариант шаблона и эксперимент. Человек должен approve.
2. **Данные-driven.** Анализирует метрики: что именно не работает — тема, тело, CTA, оффер.
3. **LLM-анализ.** LLM читает примеры отправленных писем + метрики + ICP + brief, и предлагает, что менять.
4. **Ограниченные изменения.** Не переписывать всё — менять одну переменную за раз (subject, body, CTA, tone).
5. **Human-in-the-loop.** Человек видит предложение, approve или reject. Только после approve создаётся эксперимент.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         auto-revision                 │
                    │                                       │
   analytics.alert►│  RevisionService                      │
   (из 5A)         │       │                               │
                    │       ├──► MetricsAnalyzer            │
                    │       ├──► LLMAdvisor ────────────────┼──► llm-gateway
                    │       ├──► TemplateRevisor ───────────┼──► llm-gateway
                    │       ├──► ExperimentsClient ─────────┼──► experiments-service
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - revision.proposed                 │
                    │   - revision.approved                 │
                    │   - revision.rejected                 │
                    └──────────────────────────────────────┘
```

**Модель данных:** таблица `revisions`.

---

# Задача 5B.1 — Каркас + модель Revision

**Файл:** `docs/tasks/sprint-5b/5b.1-bootstrap.md`

## Цель

Создать каркас сервиса `auto-revision`, определить модель `Revision`, миграция с RLS.

## Детали

### `models.py`

```python
class Revision(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    """Предложение по ревизии шаблона."""

    __tablename__ = "revisions"

    # Триггер
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # "low_reply_rate" | "high_bounce_rate" | "low_positive_reply_rate" | "manual"

    trigger_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {metrics: {...}, window_days: 30, template_id: "...", segment_id: "..."}

    # Что ревизуется
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template_version: Mapped[str] = mapped_column(String(16), nullable=False)
    segment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Предложение
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending | approved | rejected | superseded | applied

    diagnosis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # LLM-анализ: что не работает

    proposed_changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # [{variable_type: "subject" | "body" | "cta" | "tone", description: "...", example_before: "...", example_after: "..."}]

    proposed_template: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {system_prompt: "...", user_prompt_template: "...", variables_used: [...]}

    # Эксперимент
    experiment_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    # Ревью
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Метаданные
    llm_model: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
```

### Миграция

По образцу. RLS.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  auto-revision:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/auto-revision/Dockerfile
    container_name: outreach-auto-revision
    environment:
      <<: *common-env
      SERVICE_NAME: auto-revision
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/13
      LLM_GATEWAY_URL: http://llm-gateway:8000
      ANALYTICS_SERVICE_URL: http://analytics-service:8000
      EXPERIMENTS_SERVICE_URL: http://experiments-service:8000
      ORCHESTRATOR_URL: http://orchestrator:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      analytics-service:
        condition: service_started
      experiments-service:
        condition: service_started
    labels:
      caddy: revision.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
```

Обновить `scripts/migrate.sh`.

## Acceptance criteria

```bash
docker compose ... run --rm auto-revision alembic upgrade head
docker compose ... up -d auto-revision
curl -fsS https://revision.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\d+ revisions"
```

---

# Задача 5B.2 — MetricsAnalyzer + LLMAdvisor + TemplateRevisor

**Файл:** `docs/tasks/sprint-5b/5b.2-analysis.md`

## Цель

Реализовать три компонента:
1. **MetricsAnalyzer** — определяет, что именно не работает (subject, body, CTA, сегмент).
2. **LLMAdvisor** — через LLM анализирует и даёт диагноз.
3. **TemplateRevisor** — генерирует новую версию шаблона на основе диагноза.

## Детали

### `analysis/metrics_analyzer.py`

```python
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

import structlog


logger = structlog.get_logger()


@dataclass
class MetricsSnapshot:
    sent: int
    replied: int
    positive_replied: int
    bounced: int
    failed: int
    open_rate: float
    reply_rate: float
    positive_reply_rate: float
    bounce_rate: float
    by_segment: dict[str, dict]  # segment_id → metrics
    by_template: dict[str, dict]  # template_id:version → metrics
    best_segment_id: str | None
    worst_segment_id: str | None


class MetricsAnalyzer:
    """Собирает метрики и определяет проблемные зоны."""

    def __init__(self, analytics_client) -> None:
        self._analytics = analytics_client

    async def analyze(
        self,
        *,
        tenant_id: UUID,
        window_days: int = 30,
        template_id: str | None = None,
    ) -> MetricsSnapshot:
        to_date = date.today()
        from_date = to_date - timedelta(days=window_days)

        overview = await self._analytics.get_overview(
            tenant_id=tenant_id, from_date=from_date, to_date=to_date,
        )
        by_template = await self._analytics.get_by_template(
            tenant_id=tenant_id, from_date=from_date, to_date=to_date,
        )
        reply_categories = await self._analytics.get_reply_categories(
            tenant_id=tenant_id, from_date=from_date, to_date=to_date,
        )

        # Определяем best/worst сегмент
        by_segment = {}  # в analytics пока нет by-segment endpoint, добавим в 5B.3
        ...

        return MetricsSnapshot(
            sent=overview.get("sent", 0),
            replied=overview.get("replied", 0),
            positive_replied=overview.get("positive_replied", 0),
            bounced=overview.get("bounced", 0),
            failed=overview.get("failed", 0),
            open_rate=overview.get("open_rate", 0.0),
            reply_rate=overview.get("reply_rate", 0.0),
            positive_reply_rate=overview.get("positive_reply_rate", 0.0),
            bounce_rate=overview.get("bounce_rate", 0.0),
            by_segment=by_segment,
            by_template={t["template_id"] + ":" + t.get("template_version", "v1"): t for t in by_template},
            best_segment_id=None,
            worst_segment_id=None,
        )
```

### `analysis/llm_advisor.py`

```python
class LLMAdvisor:
    """Через LLM анализирует метрики и даёт диагноз."""

    def __init__(self, llm, settings) -> None:
        ...

    async def diagnose(
        self,
        *,
        tenant_id: str,
        metrics: MetricsSnapshot,
        template: dict,
        brief: dict,
        icp: dict,
        sample_emails: list[dict],
        trace_id: str,
    ) -> dict:
        """Возвращает {diagnosis, proposed_changes, llm_confidence}."""
        prompt = build_diagnose_prompt(
            metrics=metrics,
            template=template,
            brief=brief,
            icp=icp,
            sample_emails=sample_emails,
        )
        result = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type="auto_revision_diagnose_v1",
            system=prompt.system,
            user=prompt.user,
            output_schema=_DiagnosisSchema,
            trace_id=trace_id,
            temperature=0.3,
            max_tokens=4096,
        )
        return result.model_dump()
```

**Промпт (сокращённо):**

```
Ты — эксперт по B2B outreach. У нас проблема: метрики ниже нормы.

Метрики (окно 30 дней):
- Отправлено: {sent}
- Reply rate: {reply_rate:.2%} (норма 2-5%)
- Positive reply rate: {positive_reply_rate:.2%} (норма 0.5-2%)
- Bounce rate: {bounce_rate:.2%}

Шаблон:
{template}

Контекст (brief + ICP):
{brief_summary}
{icp_summary}

Примеры последних 10 отправленных писем:
{sample_emails}

Проанализируй и предложи 1-2 конкретных изменения. Одно изменение — одна переменная.

Верни JSON:
{
  "diagnosis": "1-2 предложения: что именно не работает",
  "proposed_changes": [
    {
      "variable_type": "subject" | "body" | "cta" | "tone",
      "description": "что меняем",
      "example_before": "как было",
      "example_after": "как будет"
    }
  ],
  "llm_confidence": 0.0
}
```

### `analysis/template_revisor.py`

```python
class TemplateRevisor:
    """Генерирует новую версию шаблона на основе диагноза."""

    async def revise(
        self,
        *,
        tenant_id: str,
        original_template: dict,
        diagnosis: dict,
        brief: dict,
        icp: dict,
        trace_id: str,
    ) -> dict:
        """Возвращает новый шаблон (system_prompt, user_prompt_template)."""
        prompt = build_revise_prompt(...)
        result = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type="auto_revision_revise_v1",
            system=prompt.system,
            user=prompt.user,
            output_schema=_RevisedTemplateSchema,
            trace_id=trace_id,
            temperature=0.5,
            max_tokens=8192,
        )
        return result.model_dump()
```

**Важно:** `TemplateRevisor` генерирует **новую версию Python-шаблона**? Или новый промпт?

**Решение:** templates — код. Но auto-revision не может писать код. Значит, шаблон должен быть **data-driven**. Нужно вынести промпты шаблонов в БД.

**Проблема:** в Спринте 3 мы решили, что шаблоны — код. Теперь для auto-revision нужны шаблоны в БД.

**Компромисс:**
- Базовые шаблоны (`email_cold_outreach_v1`) остаются в коде.
- Auto-revision создаёт **override** — хранит новый промпт в БД (`template_overrides`).
- Composer сначала проверяет `template_overrides`, потом fallback в код.

**Обновить composer-service:**
- Добавить модель `TemplateOverride` в БД.
- При `draft` — если есть override для `(template_id, version, tenant_id)` — использовать его.

**Обновить схему:**

```python
# composer-service/src/composer_service/models.py
class TemplateOverride(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "template_overrides"

    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_version: Mapped[str] = mapped_column(String(16), nullable=False)
    override_version: Mapped[str] = mapped_column(String(16), nullable=False)  # v1-override-1
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="auto-revision")
    source_revision_id: Mapped[UUID | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "template_id", "override_version", name="uq_template_override"),
    )
```

`TemplateRevisor` создаёт `TemplateOverride` через composer API. Composer использует активный override, если есть.

**Миграция в composer-service:** добавить `template_overrides`.

**Endpoint в composer:** `POST /templates/overrides` — создать override.

## Acceptance criteria

```bash
uv run pytest services/auto-revision/tests/test_metrics_analyzer.py services/auto-revision/tests/test_llm_advisor.py -v
# Ожидание: passed

# E2E
docker compose ... exec -T auto-revision python - <<'PY'
# Запустить анализ на тестовых данных
PY
```

## Подсказки

- **Templates остаются кодом, но с override в БД.** Это компромисс.
- **Один эксперимент — одно изменение.** Не менять subject и body одновременно.
- **LLM confidence** — если < 0.6, не предлагать ревизию.

## Анти-паттерны

- ❌ Не позволять LLM писать произвольный код.
- ❌ Не менять всё сразу.
- ❌ Не применять override без approve человека.

---

# Задача 5B.3 — RevisionService + API + интеграция с orchestrator

**Файл:** `docs/tasks/sprint-5b/5b.3-service.md`

## Цель

Реализовать `RevisionService`: при alert'е — собирает метрики, генерирует предложение, публикует `revision.proposed`. API для approve/reject. Интеграция с orchestrator: approve → создание эксперимента.

## Детали

### `service.py`

```python
class RevisionService:
    async def propose(
        self,
        *,
        tenant_id: UUID,
        trigger_type: str,
        trigger_context: dict,
        trace_id: str,
    ) -> Revision:
        # 1. Определяем, что ревизуем
        template_id = trigger_context.get("template_id")
        if not template_id:
            # Берём шаблон с худшими метриками
            metrics = await self._analyzer.analyze(tenant_id=tenant_id)
            template_id = self._find_worst_template(metrics)
        ...
        # 2. Собираем контекст (brief, icp, sample_emails)
        ...
        # 3. LLMAdvisor.diagnose
        diagnosis = await self._advisor.diagnose(...)
        if diagnosis["llm_confidence"] < 0.6:
            raise AppError("Low confidence in diagnosis", code="low_confidence", status_code=422)
        # 4. TemplateRevisor.revise
        proposed_template = await self._revisor.revise(...)
        # 5. Создаём Revision
        revision = Revision(
            tenant_id=tenant_id,
            trigger_type=trigger_type,
            trigger_context=trigger_context,
            template_id=template_id,
            template_version="v1",
            status="pending",
            diagnosis=diagnosis["diagnosis"],
            proposed_changes=diagnosis["proposed_changes"],
            proposed_template=proposed_template,
            llm_model=self._settings.llm_model,
            llm_confidence=diagnosis["llm_confidence"],
        )
        await self._repo.add(revision)
        await emit_revision_proposed(self._publisher, revision, trace_id=trace_id)
        return revision

    async def approve(
        self,
        *,
        tenant_id: UUID,
        revision_id: UUID,
        user_id: str,
        trace_id: str,
    ) -> Revision:
        revision = await self.get(revision_id)
        if revision.status != "pending":
            raise ValidationError(f"Cannot approve revision with status {revision.status}")

        # 1. Создаём TemplateOverride в composer
        override = await self._composer.create_template_override(
            tenant_id=str(tenant_id),
            template_id=revision.template_id,
            base_version=revision.template_version,
            override_version=f"auto-{revision.id.hex[:8]}",
            system_prompt=revision.proposed_template["system_prompt"],
            user_prompt_template=revision.proposed_template["user_prompt_template"],
            source_revision_id=revision.id,
        )

        # 2. Создаём эксперимент через experiments-service
        experiment = await self._experiments.create_experiment(
            tenant_id=str(tenant_id),
            data={
                "name": f"Auto-revision {revision.id.hex[:8]}",
                "hypothesis": revision.diagnosis,
                "variable_type": revision.proposed_changes[0]["variable_type"],
                "variable_description": revision.proposed_changes[0]["description"],
                "channel": "email",
                "variants": [
                    {"id": "control", "name": "Control", "template_id": revision.template_id, "weight": 0.5},
                    {"id": "variant", "name": "Variant", "template_id": f"{revision.template_id}-{override['override_version']}", "weight": 0.5},
                ],
                "metrics": {"primary": "positive_reply_rate", "secondary": ["reply_rate"]},
                "sample_size_per_variant": 200,
            },
        )

        revision.status = "approved"
        revision.reviewed_by = user_id
        revision.reviewed_at = datetime.now(timezone.utc)
        revision.experiment_id = UUID(experiment["id"])
        await self._repo._s.flush()

        await emit_revision_approved(self._publisher, revision, trace_id=trace_id)
        return revision

    async def reject(self, *, revision_id: UUID, user_id: str, reason: str, trace_id: str) -> Revision:
        revision = await self.get(revision_id)
        revision.status = "rejected"
        revision.reviewed_by = user_id
        revision.reviewed_at = datetime.now(timezone.utc)
        revision.rejection_reason = reason
        await self._repo._s.flush()
        await emit_revision_rejected(self._publisher, revision, trace_id=trace_id)
        return revision
```

### API

```python
@router.post("/propose", response_model=RevisionRead)
async def propose(
    data: ProposeRequest,
    svc=Depends(get_service),
) -> RevisionRead:
    """Ручной запуск предложения ревизии."""
    ...


@router.get("", response_model=list[RevisionSummary])
async def list_revisions(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc=Depends(get_service),
) -> list[RevisionSummary]:
    ...


@router.get("/{revision_id}", response_model=RevisionRead)
async def get_revision(revision_id: UUID, svc=Depends(get_service)) -> RevisionRead:
    ...


@router.post("/{revision_id}/approve", response_model=RevisionRead)
async def approve_revision(
    revision_id: UUID,
    request: Request,
    svc=Depends(get_service),
) -> RevisionRead:
    ...


@router.post("/{revision_id}/reject", response_model=RevisionRead)
async def reject_revision(
    revision_id: UUID,
    data: RejectRequest,
    request: Request,
    svc=Depends(get_service),
) -> RevisionRead:
    ...
```

### Интеграция с orchestrator

**Обновить `orchestrator/handlers/analytics_alert.py`:**

```python
class AnalyticsAlertHandler(StepHandler):
    event_type = "analytics.alert"
    step_name = "auto_revision"

    async def handle(self, envelope: EventEnvelope) -> None:
        alert = envelope.payload.get("alert", {})
        if alert.get("type") != "low_reply_rate":
            return
        if not self._settings.auto_revision_enabled:
            return

        # Создаём ревизию через auto-revision API
        revision = await self._revision_client.propose(
            tenant_id=str(envelope.tenant_id),
            trigger_type="low_reply_rate",
            trigger_context={
                "metrics": alert,
                "window_days": 30,
            },
            trace_id=envelope.trace_id,
        )
        logger.info("revision_proposed", revision_id=revision["id"], tenant_id=str(envelope.tenant_id))
```

**Добавить `auto_revision_enabled` в Settings orchestrator.**

### Обновить composer: TemplateOverride

**Миграция + модель + API `POST /templates/overrides` + логика использования в `draft`.**

**Обновить `ComposerService.draft`:**

```python
# После выбора template:
override = await self._template_override_repo.get_active(
    tenant_id=tenant_id,
    template_id=template.template_id,
)
if override is not None:
    # Используем override вместо встроенного шаблона
    rendered = self._apply_override(override, context)
else:
    rendered = template.render(context)
```

**`_apply_override`** — подставляет переменные в `user_prompt_template`.

**Это изменение Спринта 3.** Нужно вернуться и добавить.

## Acceptance criteria

```bash
# 1. Симулировать alert
docker run --rm --network outreach-net natsio/nats-box:0.16.0 \
  nats -s "nats://$NATS_USER:$NATS_PASSWORD@nats:4222" pub "analytics.alert.$TENANT" \
  '{"event_type":"analytics.alert","schema_version":"1.0","occurred_at":"2026-10-02T10:00:00Z","tenant_id":"'$TENANT'","trace_id":"t1","producer":"test/0.1","payload":{"alert":{"type":"low_reply_rate","value":0.015,"threshold":0.02,"message":"low reply rate"}}}'

# 2. Дождаться revision
sleep 30
curl -s -H "X-Tenant-ID: $TENANT" "https://revision.dev.aitler.ru/?status=pending" | jq '.[0] | {id, template_id, diagnosis, changes: .proposed_changes | length}'
# Ожидание: revision с диагнозом

# 3. Approve
REV_ID=$(curl -s -H "X-Tenant-ID: $TENANT" "https://revision.dev.aitler.ru/?status=pending" | jq -r '.[0].id')
curl -sX POST https://revision.dev.aitler.ru/$REV_ID/approve \
  -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: app-1" | jq '.status, .experiment_id'
# Ожидание: "approved", experiment_id

# 4. Override создан
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/templates/overrides | jq '.[0]'
# Ожидание: override

# 5. Эксперимент создан
curl -s -H "X-Tenant-ID: $TENANT" https://experiments.dev.aitler.ru/experiments | jq '.[0]'
# Ожидание: эксперимент

# 6. События
bash scripts/nats-cli.sh stream view BRIEFS --last 20 | grep -E "revision\."
# Ожидание: proposed, approved
```

## Подсказки

- **`template_overrides`** — ключевое изменение. Без него auto-revision не работает.
- **Один эксперимент — одна переменная.**
- **Human approve обязателен** — авто-применение опасно.

## Анти-паттерны

- ❌ Не применять override без approve.
- ❌ Не создавать несколько экспериментов из одного revision.
- ❌ Не игнорировать low confidence.

---

# Задача 5B.4 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-5b/5b.4-tests.md`

## Acceptance criteria

```bash
uv run pytest services/auto-revision/tests/ -v --cov=auto_revision --cov-report=term-missing
# Ожидание: coverage >= 80%
```

---

# 5C — `telegram-sender`

## Что такое telegram-sender и почему он сложный

Telegram — **рискованный канал**. Массовая отправка с user-аккаунта = бан за дни. Бот — только для тех, кто сам нажал /start. Поэтому:

1. **Не для холодного массового outreach.**
2. **Только для:**
   - Follow-up после email, если у контакта есть публичный TG.
   - Тех, кто сам написал боту.
   - Тех, с кем уже есть контакт.
3. **Rate limit жёсткий.** 20-30 сообщений/день на аккаунт. FloodWait от Telegram — обязательная обработка.
4. **Ротация аккаунтов.** Если несколько — распределяем.
5. **Warm-up.** Новый аккаунт начинает с 3-5 сообщений/день.

**Два подхода:**
- **Bot API** — проще, но только для тех, кто нажал /start.
- **MTProto (Telethon)** — user-аккаунт, может писать первым, но риск бана выше.

**Решение:** поддерживаем оба. Bot — по умолчанию (безопасно). MTProto — опционально, для конкретных случаев.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         telegram-sender               │
                    │                                       │
   message.approved►│  TelegramSenderService                │
                    │       │                               │
                    │       ├──► AccountManager             │
                    │       │       ├──► BotClient          │
                    │       │       └──► MTProtoClient      │
                    │       ├──► RampUpLimiter              │
                    │       ├──► FloodWaitHandler           │
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - message.sent                      │
                    │   - message.failed                    │
                    └──────────────────────────────────────┘
```

**Модель данных:** `telegram_accounts`, `telegram_send_attempts`.

---

# Задача 5C.1 — Каркас + модели

**Файл:** `docs/tasks/sprint-5c/5c.1-bootstrap.md`

## Детали

### `models.py`

```python
class TelegramAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "telegram_accounts"

    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # "bot" | "mtproto"

    # Bot
    bot_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # MTProto
    api_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_hash_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    session_string_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Общее
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    # active | paused | flood_wait | banned | error

    # Ramp-up
    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    hourly_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    warmup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # FloodWait
    flood_wait_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_telegram_accounts_phone"),
        UniqueConstraint("tenant_id", "bot_username", name="uq_telegram_accounts_bot"),
    )


class TelegramSendAttempt(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "telegram_send_attempts"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("telegram_accounts.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    # pending | sent | failed | flood_wait | blocked_by_user

    to_handle: Mapped[str] = mapped_column(String(128), nullable=False)
    to_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    telegram_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    flood_wait_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### Миграция + RLS + docker-compose

По образцу других сервисов.

### Зависимости

```toml
"telethon>=1.36",           # MTProto
"aiogram>=3.13",            # Bot API (async)
"cryptography>=43.0",
```

## Acceptance criteria

```bash
docker compose ... run --rm telegram-sender alembic upgrade head
docker compose ... up -d telegram-sender
curl -fsS https://tg.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\d+ telegram_accounts"
```

---

# Задача 5C.2 — Bot + MTProto clients + FloodWait handling

**Файл:** `docs/tasks/sprint-5c/5c.2-clients.md`

## Детали

### `clients/bot_client.py`

```python
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError


class BotClient:
    def __init__(self, token: str) -> None:
        self._bot = Bot(token=token)

    async def send(
        self,
        *,
        chat_id: int | str,
        text: str,
        parse_mode: str | None = "HTML",
    ) -> dict:
        try:
            msg = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
            return {"success": True, "message_id": msg.message_id}
        except TelegramRetryAfter as e:
            return {"success": False, "flood_wait_seconds": e.retry_after, "error": "flood_wait"}
        except TelegramForbiddenError as e:
            return {"success": False, "error": "blocked_by_user", "details": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self) -> None:
        await self._bot.session.close()
```

### `clients/mtproto_client.py`

```python
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError
from telethon.sessions import StringSession


class MTProtoClient:
    def __init__(self, *, api_id: int, api_hash: str, session_string: str) -> None:
        self._client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
        )
        self._connected = False

    async def connect(self) -> None:
        if not self._connected:
            await self._client.connect()
            self._connected = True

    async def send(
        self,
        *,
        peer: str,
        text: str,
    ) -> dict:
        await self.connect()
        try:
            msg = await self._client.send_message(peer, text, link_preview=False)
            return {"success": True, "message_id": msg.id}
        except FloodWaitError as e:
            return {"success": False, "flood_wait_seconds": e.seconds, "error": "flood_wait"}
        except UserPrivacyRestrictedError:
            return {"success": False, "error": "privacy_restricted"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self) -> None:
        if self._connected:
            await self._client.disconnect()
```

### `flood_wait.py`

```python
class FloodWaitHandler:
    """Обрабатывает FloodWait от Telegram."""

    def __init__(self, repo, redis) -> None:
        ...

    async def handle(self, *, account, seconds: int) -> None:
        # 1. Помечаем аккаунт flood_wait
        account.status = "flood_wait"
        account.flood_wait_until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        await self._repo._s.flush()

        # 2. Логируем
        logger.warning("telegram_flood_wait", account_id=str(account.id), seconds=seconds)

        # 3. Если seconds > 3600 — alert
        if seconds > 3600:
            await self._alert(...)
```

### `rampup.py`

Аналогично email-sender, но жёстче:
- День 1-3: 3 сообщения/день.
- День 4-7: 5/день.
- День 8-14: 10/день.
- День 15-30: 20/день.
- Далее: 30/день (макс).

## Acceptance criteria

```bash
uv run pytest services/telegram-sender/tests/test_bot_client.py services/telegram-sender/tests/test_mtproto_client.py -v
```

---

# Задача 5C.3 — Service + API + подписка на message.approved

**Файл:** `docs/tasks/sprint-5c/5c.3-service.md`

## Детали

### Логика

При `message.approved` (channel=telegram):
1. Получить Message из composer.
2. Проверить, что `channel == "telegram"`.
3. Найти handle в `recipient_snapshot.messenger_handle` или в `contact.messengers`.
4. Выбрать аккаунт (bot или mtproto).
5. Проверить ramp-up лимит и flood_wait.
6. Отправить.
7. Записать SendAttempt, обновить Message.

### Ограничение

**Не отправляем холодный outreach.** Если это первое сообщение контакту и у нас нет подтверждения, что он ожидает — **не отправляем**. Логика:
- Если `contact.consent.messenger_opt_in == "granted"` — можно.
- Если это follow-up после email reply — можно.
- Иначе — блокируем.

**Обновить `TelegramSenderService`:**

```python
async def send_approved_message(self, *, tenant_id, message_id, trace_id) -> SendAttempt:
    message = await self._composer.get_message(message_id, tenant_id=str(tenant_id))
    if message.get("channel") != "telegram":
        raise ValidationError("Not a telegram message")

    contact = await self._contact_store.get_contact(UUID(message["contact_id"]), tenant_id=str(tenant_id))
    consent = (contact.get("consent") or {}).get("messenger_opt_in", "unknown")
    if consent != "granted":
        # Проверяем, есть ли предыдущий reply на email
        has_reply = await self._contact_store.has_reply(contact["id"], tenant_id=str(tenant_id))
        if not has_reply:
            raise ValidationError("Cannot send cold telegram — no consent, no prior reply")
    ...
```

### API

```python
@router.post("/accounts", response_model=TelegramAccountRead, status_code=201)
async def create_account(...): ...


@router.get("/accounts", response_model=list[TelegramAccountRead])
async def list_accounts(...): ...


@router.post("/accounts/{account_id}/verify", response_model=TelegramAccountRead)
async def verify_account(...): ...


@router.post("/accounts/{account_id}/pause", response_model=TelegramAccountRead)
async def pause_account(...): ...


@router.get("/attempts", response_model=list[TelegramSendAttemptRead])
async def list_attempts(...): ...
```

## Acceptance criteria

```bash
# 1. Создать бота
curl -sX POST https://tg.dev.aitler.ru/accounts \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: acc-1" \
  -d '{"account_type":"bot","bot_token":"...","display_name":"Outreach Bot","user_id":"user-1"}' | jq .

# 2. Verify
curl -sX POST https://tg.dev.aitler.ru/accounts/$ACC_ID/verify \
  -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: v-1" | jq .status
# Ожидание: "active"

# 3. Draft с channel=telegram
# 4. Approve
# 5. Проверить отправку (если контакт с consent)
```

## Подсказки

- **Bot vs MTProto** — Bot безопаснее.
- **Consent обязателен** — иначе блокируем.
- **FloodWait — обрабатывать обязательно.** Помечаем аккаунт, retry через N секунд.
- **Ramp-up жёстче, чем email.** Telegram банит быстрее.

## Анти-паттерны

- ❌ Не отправлять без consent.
- ❌ Не игнорировать FloodWait.
- ❌ Не использовать MTProto для массового холодного outreach.

---

# Задача 5C.4 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-5c/5c.4-tests.md`

## Acceptance criteria

```bash
uv run pytest services/telegram-sender/tests/ -v --cov=telegram_sender --cov-report=term-missing
# Ожидание: coverage >= 80%
```

---

## Финальная E2E-проверка Спринта 5

```bash
export TENANT="<sandbox>"

# 1. Полный flow: brief → ICP → sourcing → drafts → approve → send
BRIEF_ID=$(curl -sX POST https://brief.dev.aitler.ru/briefs \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-b1" \
  -d '{"text": "Производим гидроборты, ищем дистрибьюторов."}' | jq -r .id)

# Ответить на вопросы
for i in $(seq 0 10); do
  STATUS=$(curl -s -H "X-Tenant-ID: $TENANT" https://brief.dev.aitler.ru/briefs/$BRIEF_ID | jq -r .status)
  [ "$STATUS" = "complete" ] && break
  PENDING=$(curl -s -H "X-Tenant-ID: $TENANT" https://brief.dev.aitler.ru/briefs/$BRIEF_ID | jq '[.qa_history | to_entries[] | select(.value.answered_at == null) | .key][0]')
  [ "$PENDING" = "null" ] && break
  curl -sX POST https://brief.dev.aitler.ru/briefs/$BRIEF_ID/answers \
    -H "Content-Type: application/json" -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: a-$i" \
    -d "{\"question_index\": $PENDING, \"answer\": \"Ответ $i\"}" > /dev/null
done

# 2. Orchestrator должен автоматически запустить ICP + sourcing
sleep 60
curl -s -H "X-Tenant-ID: $TENANT" "https://orchestrator.dev.aitler.ru/flows?brief_id=$BRIEF_ID" | jq '.[0] | {status, current_step, icp_id, search_job_id, completed_steps, total_steps}'
# Ожидание: status=running/paused, completed_steps >= 2

# 3. Проверить, что ICP создан
curl -s -H "X-Tenant-ID: $TENANT" "https://icp.dev.aitler.ru/icps?brief_id=$BRIEF_ID" | jq 'length'
# Ожидание: >= 1

# 4. Ручной trigger-draft
FLOW_ID=$(curl -s -H "X-Tenant-ID: $TENANT" "https://orchestrator.dev.aitler.ru/flows?brief_id=$BRIEF_ID" | jq -r '.[0].id')
curl -sX POST https://orchestrator.dev.aitler.ru/flows/$FLOW_ID/trigger-draft \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: td-1" \
  -d '{"channel":"email","template_id":"email_cold_outreach","sender_config":{"sender_from_name":"Сергей","sender_from_email":"s@example.com","sender_signature":"Сергей"}}' | jq .status

# 5. Дождаться drafts
sleep 120
curl -s -H "X-Tenant-ID: $TENANT" "https://composer.dev.aitler.ru/messages?limit=10" | jq 'length'
# Ожидание: >= 1

# 6. Flow завершён или paused
curl -s -H "X-Tenant-ID: $TENANT" https://orchestrator.dev.aitler.ru/flows/$FLOW_ID | jq '{status, completed_steps, total_steps}'
# Ожидание: completed_steps >= 3

# 7. Симулировать alert low_reply_rate
docker run --rm --network outreach-net natsio/nats-box:0.16.0 \
  nats -s "nats://$NATS_USER:$NATS_PASSWORD@nats:4222" pub "analytics.alert.$TENANT" \
  '{"event_type":"analytics.alert",...}'

# 8. Дождаться revision
sleep 30
curl -s -H "X-Tenant-ID: $TENANT" "https://revision.dev.aitler.ru/?status=pending" | jq 'length'
# Ожидание: >= 1

# 9. Approve revision
REV_ID=$(curl -s -H "X-Tenant-ID: $TENANT" "https://revision.dev.aitler.ru/?status=pending" | jq -r '.[0].id')
curl -sX POST https://revision.dev.aitler.ru/$REV_ID/approve \
  -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: app-1" | jq '{status, experiment_id}'
# Ожидание: approved, experiment_id

# 10. Проверить override в composer
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/templates/overrides | jq 'length'
# Ожидание: >= 1

# 11. Проверить эксперимент
curl -s -H "X-Tenant-ID: $TENANT" https://experiments.dev.aitler.ru/experiments | jq '.[0] | {name, status}'
# Ожидание: эксперимент

# 12. Telegram sender
# Создать бота, verify
curl -sX POST https://tg.dev.aitler.ru/accounts ... | jq .

# 13. Метрики orchestrator
curl -s https://orchestrator.dev.aitler.ru/metrics | grep orchestrator_ | head -20

# 14. CI
git push origin develop
# Зелёные
```

**Если все 14 пунктов проходят — Спринт 5 закрыт.**

---

## Проверка: что я перепроверил

- [x] Порядок задач: 5A.1 → 5A.2 → 5A.3 → 5A.4 → 5A.5 → 5B.1 → 5B.2 → 5B.3 → 5B.4 → 5C.1 → 5C.2 → 5C.3 → 5C.4, зависимости соблюдены.
- [x] Orchestrator: EventRouter + handlers + retry + observability.
- [x] Handlers сами создают session после получения tenant_id из envelope.
- [x] Проверка `flow.status == "running"` во всех handlers.
- [x] Retry через `next_retry_at` + exponential backoff.
- [x] Prometheus `/metrics`.
- [x] Auto-revision: MetricsAnalyzer + LLMAdvisor + TemplateRevisor.
- [x] `template_overrides` в composer — критичное изменение Спринта 3.
- [x] Human-in-the-loop для revision — approve обязателен.
- [x] Один эксперимент — одна переменная.
- [x] Telegram sender: Bot + MTProto, FloodWait handling, ramp-up.
- [x] Consent обязателен для Telegram.
- [x] События: flow.*, revision.*.
- [x] Mypy strict, ruff, pytest.
- [x] Никаких cross-service импортов.
- [x] Idempotency-Key на всех POST.
- [x] RLS на всех таблицах.

---

## Что дальше (Спринт 6)

После Спринта 5 платформа **функционально полная и самоуправляемая**:
- Brief → ICP → sourcing → composer → review → sender → reply → analytics → experiments → auto-revision — всё автоматически.
- Два канала (email + Telegram).
- Обратная связь замыкается.

**Спринт 6** — улучшения и расширения:
- LinkedIn sender (рискованный).
- WhatsApp sender (Business API).
- Мульти-armed bandit для экспериментов (вместо классического A/B).
- ML-модели для скоринга контактов.
- Multi-region deploy.
- Per-tenant настройки automation levels.
- Web UI (Next.js или Streamlit) для дашбордов и управления.

**Что от тебя нужно сейчас:**
1. Разложить эти 13 задач по файлам в `docs/tasks/sprint-5/` (5A, 5B, 5C — три подпапки).
2. Дать агенту: «Начинай с 5A.1. 5A — обязательно до конца (orchestrator), потом 5B (auto-revision), потом 5C (telegram)».
3. Сообщить мне, когда Спринт 5 закрыт (или если агент застрял — особенно на 5A.2, там handlers с session management).

**Критичный вопрос к тебе:**
- **`template_overrides` в composer** — это изменение Спринта 3. Придётся вернуться в composer-service и добавить модель + миграцию + API. Это ~3 задачи. Или отложить auto-revision до Спринта 6, а в 5B сделать только analysis без применения. **Рекомендую добавить override — без него auto-revision бессмысленен.**
- **Telegram Bot vs MTProto** — какой использовать по умолчанию? Bot безопаснее, но ограничен. MTProto мощнее, но риск. **Рекомендую Bot по умолчанию, MTProto — опционально для конкретных tenant'ов.**

Если хочешь что-то поправить сейчас — скажи.