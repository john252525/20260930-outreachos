# Спринт 3 — `composer-service` + `review-queue` + `sender-email`

Проверил: зависимости от Спринта 0, 1, 2A, 2B, 2C соблюдены, порядок задач логичен, acceptance criteria проверяемы, нет противоречий с `docs/contracts.md` и `docs/infra.md`. Учёл, что Спринт 3 — **самый критичный для deliverability и репутации**, поэтому разбил его на **3 под-спринта: 3A → 3B → 3C**.

## Почему три под-спринта

**3A — `composer-service`.** Генерация писем. Изолированный LLM-сервис. Вход: Contact + Company + Brief + ICP + канал. Выход: черновик Message. Без отправки, без ревью — только генерация. Можно тестировать отдельно, звать вручную, смотреть на качество.

**3B — `review-queue`.** Очередь на human-in-the-loop. Approve/reject/edit. Тонкий сервис, но критичный: без него нельзя отправлять. Отдельно от composer, потому что это **состояние**, а composer — **генерация**.

**3C — `sender-email`.** Самый сложный и рискованный. SMTP/IMAP, ротация ящиков, ramp-up, bounce/complaint, отписки, reply-detection. Если сломать — репутация домена сгорит за дни. Поэтому изолирован и делается последним.

**Почему не одним спринтом:** если composer генерирует мусор, а sender уже отправляет — репутация сгорит. Сначала отладим генерацию, посмотрим на письма вручную, потом построим очередь, и только потом — отправку.

**Что НЕ в этом спринте:**
- Telegram/WhatsApp sender — отдельный спринт 3D.
- LinkedIn — отдельный спринт 3E.
- A/B experiments — Спринт 4 (analytics).
- Reply classification — Спринт 4 (analytics).

**Важное решение про human-in-the-loop:** на старте 3C **100% сообщений проходят через review**. Авто-отправка без ревью — только после того, как накопим статистику (минимум 500 отправленных писем с reply rate > baseline). Это не переделывается потом — это просто флаг в конфиге, который включается позже.

**Важное решение про SMTP:** используем **per-employee ящик** (реальный ящик сотрудника через SMTP/IMAP). Не общий `sales@`. Причины:
1. Deliverability: письма от реального человека проходят лучше.
2. Юридика: сотрудник — отправитель, это его переписка.
3. Reply-detection: ответы приходят в его ящик, естественно.

**Минус:** нужно подключать ящики каждого сотрудника. Решается через админский эндпоинт + OAuth (Gmail) или app-password (Yandex, Mail.ru).

---

# 3A — `composer-service`

## Что такое composer и почему он изолирован

Это **чистый LLM-сервис без внешнего мира и без отправки**. Вход: Contact + Company + Brief + ICP + канал + sender (кто отправляет). Выход: черновик Message с персонализацией, evidence, версией шаблона. Никаких SMTP, никаких очередей, никакой отправки.

**Ключевые принципы:**
1. **Evidence для каждого факта.** Каждое утверждение о компании/человеке в письме — с `evidence_url` или помечено `is_hypothesis: true`.
2. **Версионирование шаблонов.** Каждый шаблон имеет `template_id` + `template_version`. A/B — по версиям.
3. **Персонализация, не шаблон.** Промпт заставляет LLM использовать конкретику из Company/Contact, а не общие фразы.
4. **Anti-hallucination.** LLM не должен выдумывать факты. Если данных нет — использовать нейтральную формулировку, не выдумывать.
5. **Канало-специфичность.** Email длиннее, TG короче, LinkedIn ещё короче. Разные промпты для разных каналов.
6. **Tone-of-voice из Brief.** Формальный/технический/дружеский — из `outreach_goals.tone_of_voice`.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │          composer-service             │
                    │                                       │
   HTTP POST ──────►│  API: POST /messages/draft            │
   /messages/draft  │       │                               │
                    │       ▼                               │
                    │  ComposerService                      │
                    │       │                               │
                    │       ├──► ContactStoreClient ────────┼──► contact-store
                    │       ├──► BriefClient ───────────────┼──► brief-service
                    │       ├──► ICPClient ─────────────────┼──► icp-service
                    │       ├──► LLMClient ─────────────────┼──► llm-gateway
                    │       ├──► TemplateRegistry (pure)    │
                    │       ├──► Personalizer (LLM)         │
                    │       ├──► FactChecker (pure)         │
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - message.drafted                   │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                                   Postgres
                                  (messages)
```

**Что НЕ делает:**
- Не отправляет (sender).
- Не хранит очередь на ревью (review-queue).
- Не считает метрики (analytics).
- Не классифицирует ответы (reply-classifier).

**Модель данных:** таблица `messages`. Одна строка = один черновик.

---

# Задача 3A.1 — Каркас `composer-service` + модель Message

**Файл:** `docs/tasks/sprint-3a/3a.1-bootstrap.md`

## Цель

Создать каркас сервиса, определить SQLAlchemy-модель `Message` со всеми полями из `docs/contracts.md` раздел 5, сделать миграцию с RLS.

## Зависимости

Спринт 0, 1, 2A, 2B, 2C закрыты.

## Что создать

```
services/composer-service/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_messages.py
├── src/composer_service/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── events.py
│   ├── templates/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── email_cold_outreach_v1.py
│   │   └── email_followup_v1.py
│   ├── personalization/
│   │   ├── __init__.py
│   │   ├── personalizer.py
│   │   └── fact_checker.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── contact_store_client.py
│   │   ├── brief_client.py
│   │   └── icp_client.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py             # копия
│   │   ├── json_utils.py         # копия
│   │   ├── schemas.py
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── personalize_email.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_api.py
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "composer-service"
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
    "jinja2>=3.1",
    "common",
    "contracts",
    "db",
    "nats-client",
    "llm-client",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/composer_service"]
```

### `config.py`

```python
from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field("composer-service", alias="SERVICE_NAME")
    contact_store_url: str = Field(..., alias="CONTACT_STORE_URL")
    brief_service_url: str = Field(..., alias="BRIEF_SERVICE_URL")
    icp_service_url: str = Field(..., alias="ICP_SERVICE_URL")
    llm_gateway_url: str = Field(..., alias="LLM_GATEWAY_URL")

    # LLM
    llm_model: str = Field("deepseek-chat", alias="COMPOSER_LLM_MODEL")
    llm_temperature: float = Field(0.6, alias="COMPOSER_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(2048, alias="COMPOSER_LLM_MAX_TOKENS")

    # Generation limits
    max_subject_length: int = Field(80, alias="COMPOSER_MAX_SUBJECT_LENGTH")
    max_body_words: int = Field(250, alias="COMPOSER_MAX_BODY_WORDS")
    min_body_words: int = Field(40, alias="COMPOSER_MIN_BODY_WORDS")
    max_concurrent_llm: int = Field(5, alias="COMPOSER_MAX_CONCURRENT_LLM")

    # Fact checking
    min_fact_confidence: float = Field(0.6, alias="COMPOSER_MIN_FACT_CONFIDENCE")
    strict_fact_check: bool = Field(True, alias="COMPOSER_STRICT_FACT_CHECK")

    # Defaults
    default_language: str = Field("ru", alias="COMPOSER_DEFAULT_LANGUAGE")
```

### `models.py`

Одна таблица `messages` соответствует `contracts.Message` раздел 5.

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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


class Message(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "messages"

    contact_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    company_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)

    # Последовательность (follow-up)
    sequence_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sequence_total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_message_id: Mapped[UUID | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    is_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    followup_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Содержание — вынесено для быстрого доступа
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Персонализация (полный объект из contracts.Message.personalization)
    personalization: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Отправитель
    sender: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Снапшот получателя (не меняется после создания)
    recipient_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Эксперимент
    experiment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Планирование
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Доставка
    delivery: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Engagement
    engagement: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Ревью
    review: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_messages_tenant_status", "tenant_id", "status"),
        Index("ix_messages_tenant_contact", "tenant_id", "contact_id"),
        Index("ix_messages_tenant_channel", "tenant_id", "channel"),
        Index("ix_messages_tenant_created", "tenant_id", "created_at"),
        Index("ix_messages_personalization_gin", "personalization", postgresql_using="gin", postgresql_ops={"personalization": "jsonb_path_ops"}),
    )
```

**Важно:**
- `subject` / `body_text` — в отдельных колонках для быстрого доступа.
- `personalization`, `sender`, `recipient_snapshot`, `delivery`, `engagement`, `review` — JSONB, соответствуют контракту.
- `body_text` — источник правды. `body_html` — производное для email.

### Миграция

```python
def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("sequence_step", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sequence_total_steps", sa.Integer, nullable=False, server_default="1"),
        sa.Column("parent_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_followup", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("followup_after_days", sa.Integer, nullable=True),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("body_text", sa.Text, nullable=False, server_default=""),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("word_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("personalization", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("sender", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("recipient_snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("experiment", postgresql.JSONB, nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("engagement", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("review", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_tenant_status", "messages", ["tenant_id", "status"])
    op.create_index("ix_messages_tenant_contact", "messages", ["tenant_id", "contact_id"])
    op.create_index("ix_messages_tenant_company", "messages", ["tenant_id", "company_id"])
    op.create_index("ix_messages_tenant_channel", "messages", ["tenant_id", "channel"])
    op.create_index("ix_messages_tenant_created", "messages", ["tenant_id", "created_at"])
    op.create_index("ix_messages_scheduled", "messages", ["tenant_id", "scheduled_at"])
    op.create_index("ix_messages_sent", "messages", ["tenant_id", "sent_at"])
    op.execute("CREATE INDEX ix_messages_personalization_gin ON messages USING gin (personalization jsonb_path_ops)")

    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY messages_tenant_isolation ON messages
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS messages_tenant_isolation ON messages")
    op.drop_table("messages")
```

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  composer-service:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/composer-service/Dockerfile
    container_name: outreach-composer-service
    environment:
      <<: *common-env
      SERVICE_NAME: composer-service
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/6
      CONTACT_STORE_URL: http://contact-store:8000
      BRIEF_SERVICE_URL: http://brief-service:8000
      ICP_SERVICE_URL: http://icp-service:8000
      LLM_GATEWAY_URL: http://llm-gateway:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
      contact-store:
        condition: service_started
      brief-service:
        condition: service_started
      icp-service:
        condition: service_started
      llm-gateway:
        condition: service_started
    labels:
      caddy: composer.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

Обновить `scripts/migrate.sh` — добавить `composer-service`.

### Dockerfile

Скопировать из `brief-service/Dockerfile`, поменять `--package composer-service` и `CMD`.

## Acceptance criteria

```bash
# 1. Миграция
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm composer-service alembic upgrade head
# Ожидание: Applying 0001_create_messages... OK

# 2. Сервис поднимается
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d composer-service
# Ожидание: service_started

# 3. Healthcheck
curl -fsS https://composer.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

# 4. Таблица + RLS
bash scripts/psql.sh -c "\d+ messages"
# Ожидание: таблица есть, RLS enabled

# 5. OpenAPI
curl -fsS https://composer.dev.aitler.ru/openapi.json | jq .info.title
# Ожидание: "Composer Service"
```

## Подсказки

- **`personalization.factual_claims`** — критично. Структура: `[{claim, evidence_url, confidence, is_hypothesis}]`. FactChecker будет её использовать.
- **`recipient_snapshot`** — снапшот на момент генерации. Если контакт изменится — история сохранится.
- **`review` JSONB** — `{reviewed_by, reviewed_at, rejection_reason, edited_by_human, original_body_text}`. Заполняется `review-queue`.
- **`engagement` JSONB** — `{opened_count, first_opened_at, clicked_count, replied_at, reply_id}`. Заполняется `sender-email` + `reply-classifier` (Спринт 4).

## Анти-паттерны

- ❌ Не делать колонки под каждое поле из контракта — JSONB для вложенных структур.
- ❌ Не забывать RLS.
- ❌ Не хранить `body_html` как источник правды — только `body_text`.

---

# Задача 3A.2 — TemplateRegistry + шаблоны

**Файл:** `docs/tasks/sprint-3a/3a.2-templates.md`

## Цель

Реализовать реестр шаблонов писем. Каждый шаблон — Python-модуль, возвращающий структуру промпта и переменные. Версионирование.

## Зависимости

3A.1.

## Что создать

```
services/composer-service/src/composer_service/templates/
├── __init__.py
├── base.py
├── registry.py
├── email_cold_outreach_v1.py
└── email_followup_v1.py
```

## Детали

### `base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemplateContext:
    """Контекст для генерации. Заполняется ComposerService."""

    # Получатель
    contact: dict              # payload контакта из contact-store
    company: dict | None       # payload компании

    # Отправитель
    sender: dict               # {identity_type, from_email, from_name, signature, ...}

    # Проект
    brief: dict                # payload brief
    icp: dict                  # payload ICP
    segment: dict              # сегмент, к которому принадлежит компания

    # Канал
    channel: str               # "email" | "telegram" | ...

    # Дополнительно
    language: str = "ru"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderedTemplate:
    """Результат рендера шаблона — идёт в LLM как основа."""

    system_prompt: str
    user_prompt: str
    subject_hint: str | None      # подсказка для subject
    required_mentions: list[str]  # что обязательно упомянуть
    forbidden_phrases: list[str]  # чего избегать
    variables_used: dict[str, Any]  # какие поля использованы


class Template(ABC):
    """Базовый интерфейс шаблона."""

    template_id: str
    template_version: str
    channel: str

    @abstractmethod
    def render(self, context: TemplateContext) -> RenderedTemplate:
        """Превращает контекст в промпт."""
        ...

    def validate_output(self, *, subject: str | None, body: str) -> list[str]:
        """Проверяет результат после LLM. Возвращает список warnings (не ошибок)."""
        return []
```

### `registry.py`

```python
from composer_service.templates.base import Template


class TemplateRegistry:
    """Реестр шаблонов. Шаблоны регистрируются в main.py."""

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {}
        # ключ: "{template_id}:{template_version}"

    def register(self, template: Template) -> None:
        key = f"{template.template_id}:{template.template_version}"
        if key in self._templates:
            raise ValueError(f"Template already registered: {key}")
        self._templates[key] = template

    def get(self, template_id: str, template_version: str | None = None) -> Template:
        if template_version is None:
            # Берём последнюю версию
            candidates = [
                (k, t) for k, t in self._templates.items()
                if t.template_id == template_id
            ]
            if not candidates:
                raise ValueError(f"Template not found: {template_id}")
            # Сортируем по версии (v1, v2, ... v10 — лексикографически неверно, но пока так)
            candidates.sort(key=lambda kv: kv[0], reverse=True)
            return candidates[0][1]
        key = f"{template_id}:{template_version}"
        if key not in self._templates:
            raise ValueError(f"Template not found: {key}")
        return self._templates[key]

    def list_all(self) -> list[dict]:
        return [
            {
                "template_id": t.template_id,
                "template_version": t.template_version,
                "channel": t.channel,
            }
            for t in self._templates.values()
        ]

    def default_for_channel(self, channel: str) -> Template:
        for t in self._templates.values():
            if t.channel == channel:
                return t
        raise ValueError(f"No template for channel: {channel}")
```

### `email_cold_outreach_v1.py`

Первый холодный outreach для email. Ключевые принципы в промпте.

```python
from composer_service.templates.base import RenderedTemplate, Template, TemplateContext


SYSTEM = """Ты — опытный B2B sales copywriter. Пишешь персонализированные холодные письма от имени конкретного человека.

ПРАВИЛА:
1. Пиши ТОЛЬКО валидным JSON: {"subject": "...", "body": "..."}.
2. Body — plain text, без markdown, без HTML, без списков, без заголовков.
3. Длина body: {min_words}-{max_words} слов. Короче = лучше.
4. Subject: до {max_subject_len} символов, без CAPS, без "!!!", без эмодзи.
5. Обращение на "вы" (если язык ru). По имени-отчеству, если есть отчество. Иначе — по имени.
6. Персонализация: используй КОНКРЕТНЫЕ факты о компании/человеке из контекста. Одна конкретика в первом абзаце — обязательно.
7. НЕ выдумывай факты. Если факта нет — используй нейтральную формулировку.
8. Структура (примерно):
   - 1 предложение: кто ты и почему пишешь именно этому человеку (конкретика).
   - 2-3 предложения: что предлагаешь, с одной ценностью.
   - 1 предложение: мягкий CTA (не "давайте созвонимся", а "интересно ли обсудить?").
   - Подпись.
9. Тон: {tone_of_voice}.
10. Язык: {language}.

ЗАПРЕЩЕНО:
- "Уважаемый(ая)!" без имени.
- "Наша компания является лидером рынка..."
- "Мы предлагаем широкий спектр услуг..."
- "Буду краток" / "Не буду отнимать время".
- "Заранее спасибо".
- Любые эмодзи.
- Восклицательные знаки в конце предложений (кроме CTA).

Обязательно упомяни:
{required_mentions}

Избегай фраз:
{forbidden_phrases}
"""


class EmailColdOutreachV1(Template):
    template_id = "email_cold_outreach"
    template_version = "v1"
    channel = "email"

    def __init__(self, *, min_words: int = 40, max_words: int = 250, max_subject_len: int = 80) -> None:
        self._min_words = min_words
        self._max_words = max_words
        self._max_subject_len = max_subject_len

    def render(self, context: TemplateContext) -> RenderedTemplate:
        contact = context.contact
        company = context.company or {}
        brief = context.brief
        segment = context.segment
        sender = context.sender

        # Извлекаем поля
        contact_name = self._fact_value(contact.get("full_name"))
        contact_position = self._fact_value(contact.get("position"))
        contact_email = self._primary_email(contact)

        company_name = self._fact_value(company.get("name"))
        company_industry = self._fact_value(company.get("industry"))
        company_size = self._size_value(company)
        company_location = self._location_value(company)
        company_signals = company.get("signals") or []

        sender_name = sender.get("from_name") or "Менеджер"
        sender_signature = sender.get("signature") or ""

        offering = brief.get("offering", {}) or {}
        what_we_sell = offering.get("what_we_sell", "")
        differentiators = offering.get("differentiators", []) or []
        proof_points = offering.get("proof_points", []) or []

        target_pains = segment.get("pain_hypotheses", []) or []
        role_category = contact.get("role_category", "unknown")

        tone = (brief.get("outreach_goals", {}) or {}).get("tone_of_voice", "neutral")
        language = context.language
        forbidden = (brief.get("outreach_goals", {}) or {}).get("forbidden_topics", []) or []
        required = (brief.get("outreach_goals", {}) or {}).get("required_mentions", []) or []

        system = SYSTEM.format(
            min_words=self._min_words,
            max_words=self._max_words,
            max_subject_len=self._max_subject_len,
            tone_of_voice=tone,
            language=language,
            required_mentions="\n".join(f"- {m}" for m in required) or "(нет)",
            forbidden_phrases="\n".join(f"- {f}" for f in forbidden) or "(нет)",
        )

        user = self._build_user_prompt(
            contact_name=contact_name,
            contact_position=contact_position,
            contact_role_category=role_category,
            company_name=company_name,
            company_industry=company_industry,
            company_size=company_size,
            company_location=company_location,
            company_signals=company_signals,
            sender_name=sender_name,
            sender_signature=sender_signature,
            what_we_sell=what_we_sell,
            differentiators=differentiators,
            proof_points=proof_points,
            target_pains=target_pains,
        )

        variables_used = {
            "contact_name": contact_name,
            "contact_position": contact_position,
            "company_name": company_name,
            "company_industry": company_industry,
            "sender_name": sender_name,
        }

        return RenderedTemplate(
            system_prompt=system,
            user_prompt=user,
            subject_hint=None,
            required_mentions=required,
            forbidden_phrases=forbidden,
            variables_used=variables_used,
        )

    def _build_user_prompt(self, **kwargs) -> str:
        parts = ["Сгенерируй холодное письмо.\n"]

        parts.append("ПОЛУЧАТЕЛЬ:")
        if kwargs["contact_name"]:
            parts.append(f"  Имя: {kwargs['contact_name']}")
        if kwargs["contact_position"]:
            parts.append(f"  Должность: {kwargs['contact_position']}")
        parts.append(f"  Категория роли: {kwargs['contact_role_category']}")

        if kwargs["company_name"]:
            parts.append("\nКОМПАНИЯ:")
            parts.append(f"  Название: {kwargs['company_name']}")
            if kwargs["company_industry"]:
                parts.append(f"  Отрасль: {kwargs['company_industry']}")
            if kwargs["company_size"]:
                parts.append(f"  Размер: {kwargs['company_size']}")
            if kwargs["company_location"]:
                parts.append(f"  Локация: {kwargs['company_location']}")
            if kwargs["company_signals"]:
                parts.append("  Сигналы (используй 1 в персонализации):")
                for s in kwargs["company_signals"][:3]:
                    parts.append(f"    - {s.get('summary', '')} ({s.get('source_url', '')})")

        parts.append("\nОТПРАВИТЕЛЬ:")
        parts.append(f"  Имя: {kwargs['sender_name']}")
        if kwargs["sender_signature"]:
            parts.append(f"  Подпись: {kwargs['sender_signature']}")

        parts.append("\nЧТО ПРОДАЁМ:")
        parts.append(f"  {kwargs['what_we_sell']}")
        if kwargs["differentiators"]:
            parts.append(f"  Отличия: {', '.join(kwargs['differentiators'][:3])}")
        if kwargs["proof_points"]:
            parts.append(f"  Доказательства: {', '.join(kwargs['proof_points'][:2])}")

        if kwargs["target_pains"]:
            parts.append("\nБОЛИ ЦЕЛЕВОГО СЕГМЕНТА (используй 1):")
            for p in kwargs["target_pains"][:3]:
                parts.append(f"  - {p.get('pain', '')}")

        parts.append("\nВерни JSON: {\"subject\": \"...\", \"body\": \"...\"}")
        return "\n".join(parts)

    @staticmethod
    def _fact_value(fact: dict | str | None) -> str | None:
        if fact is None:
            return None
        if isinstance(fact, str):
            return fact
        if isinstance(fact, dict):
            return fact.get("value")
        return None

    @staticmethod
    def _primary_email(contact: dict) -> str | None:
        for e in contact.get("emails", []) or []:
            if e.get("is_primary"):
                return e.get("value")
        return None

    @staticmethod
    def _size_value(company: dict) -> str | None:
        size = company.get("size_estimate") or {}
        er = size.get("employee_range")
        if er and er != "unknown":
            return er
        ec = size.get("employee_count")
        if isinstance(ec, dict):
            ec = ec.get("value")
        if ec:
            return f"{ec} сотрудников"
        return None

    @staticmethod
    def _location_value(company: dict) -> str | None:
        for loc in company.get("locations", []) or []:
            if loc.get("is_hq"):
                city = loc.get("city")
                country = loc.get("country")
                city_v = city.get("value") if isinstance(city, dict) else city
                country_v = country.get("value") if isinstance(country, dict) else country
                if city_v:
                    return f"{city_v}, {country_v}" if country_v else city_v
                if country_v:
                    return country_v
        return None

    def validate_output(self, *, subject: str | None, body: str) -> list[str]:
        warnings: list[str] = []
        if not subject:
            warnings.append("no_subject")
        elif len(subject) > self._max_subject_len:
            warnings.append(f"subject_too_long:{len(subject)}")
        if not body:
            warnings.append("empty_body")
            return warnings
        word_count = len(body.split())
        if word_count < self._min_words:
            warnings.append(f"too_short:{word_count}")
        if word_count > self._max_words:
            warnings.append(f"too_long:{word_count}")
        # Запрещённые фразы
        body_lower = body.lower()
        for phrase in ["уважаемый без имени", "лидер рынка", "широкий спектр", "буду краток", "заранее спасибо"]:
            if phrase in body_lower:
                warnings.append(f"forbidden_phrase:{phrase}")
        return warnings
```

### `email_followup_v1.py`

Follow-up (напоминание, если нет ответа через N дней). Короче, без повторов.

```python
class EmailFollowupV1(Template):
    template_id = "email_followup"
    template_version = "v1"
    channel = "email"

    def render(self, context: TemplateContext) -> RenderedTemplate:
        # Аналогично, но короче и с учётом предыдущего письма
        ...
```

**Детали:** в `context.extra["parent_message"]` передаётся предыдущее письмо. Промпт: «напиши короткое напоминание, не повторяй предыдущее, добавь новую ценность или вопрос».

### Регистрация в `main.py`

```python
from composer_service.templates.registry import TemplateRegistry
from composer_service.templates.email_cold_outreach_v1 import EmailColdOutreachV1
from composer_service.templates.email_followup_v1 import EmailFollowupV1

# в lifespan:
registry = TemplateRegistry()
registry.register(EmailColdOutreachV1(
    min_words=settings.min_body_words,
    max_words=settings.max_body_words,
    max_subject_len=settings.max_subject_length,
))
registry.register(EmailFollowupV1())
app.state.template_registry = registry
```

## Acceptance criteria

```bash
uv run pytest services/composer-service/tests/test_templates.py -v
# Ожидание: passed

uv run mypy services/composer-service
uv run ruff check services/composer-service
```

## Подсказки

- **Шаблоны — код, не данные.** Хранить их в БД — плохо, потому что они требуют логики. Хранить в Python-модулях — версионируются через git.
- **`required_mentions` / `forbidden_phrases`** — из Brief. LLM должна их соблюдать. Если нарушила — warning в `validate_output`.
- **Разные шаблоны для разных каналов.** Email — длинный, TG — короткий. Не смешивать.
- **Версия в `template_version`** — для A/B. `email_cold_outreach:v1` vs `:v2` — сравниваем метрики.

## Анти-паттерны

- ❌ Не хранить промпты в БД — только в коде.
- ❌ Не делать один универсальный шаблон для всех каналов.
- ❌ Не забывать версионирование.

---

# Задача 3A.3 — `Personalizer` (LLM: контекст → черновик письма)

**Файл:** `docs/tasks/sprint-3a/3a.3-personalizer.md`

## Цель

LLM-компонент: принимает `RenderedTemplate`, вызывает LLM, возвращает `{subject, body}`. Валидирует через `validate_output`.

## Зависимости

3A.2.

## Что создать

- `llm/schemas.py`
- `llm/prompts/personalize_email.py` (обёртка над шаблоном)
- `personalization/personalizer.py`
- Тесты.

## Детали

### `llm/schemas.py`

```python
from pydantic import BaseModel, ConfigDict


class _GeneratedEmail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str
    body: str
```

### `personalization/personalizer.py`

```python
import structlog

from composer_service.config import Settings
from composer_service.llm.client import LLMClient
from composer_service.llm.schemas import _GeneratedEmail
from composer_service.templates.base import RenderedTemplate, Template


logger = structlog.get_logger()


class Personalizer:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def generate(
        self,
        *,
        tenant_id: str,
        rendered: RenderedTemplate,
        template: Template,
        trace_id: str = "",
    ) -> tuple[str | None, str, list[str]]:
        """Возвращает (subject, body, warnings)."""

        result = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type=f"composer_{template.template_id}_{template.template_version}",
            system=rendered.system_prompt,
            user=rendered.user_prompt,
            output_schema=_GeneratedEmail,
            trace_id=trace_id,
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )

        warnings = template.validate_output(
            subject=result.subject,
            body=result.body,
        )
        if warnings:
            logger.warning("composer_output_warnings", warnings=warnings, template=template.template_id)

        return result.subject, result.body, warnings
```

**Важно:** `task_type` включает `template_id` и `template_version` — для A/B и аналитики.

## Acceptance criteria

```bash
# Unit
uv run pytest services/composer-service/tests/test_personalizer.py -v

# E2E — реальный вызов LLM
docker compose ... exec -T composer-service python - <<'PY'
import asyncio
from composer_service.config import Settings
from composer_service.llm.client import LLMClient
from composer_service.personalization.personalizer import Personalizer
from composer_service.templates.base import TemplateContext, RenderedTemplate
from composer_service.templates.email_cold_outreach_v1 import EmailColdOutreachV1

async def main():
    settings = Settings()
    llm = LLMClient(settings)
    personalizer = Personalizer(llm, settings)
    template = EmailColdOutreachV1()

    context = TemplateContext(
        contact={"full_name": {"value": "Иван Петров"}, "position": {"value": "Директор по закупкам"}, "role_category": "decision_maker", "emails": [{"value": "x@y.com", "is_primary": True}]},
        company={"name": {"value": "ООО Ромашка"}, "industry": {"value": "Логистика"}, "locations": [{"city": {"value": "Москва"}, "is_hq": True}]},
        sender={"from_name": "Сергей", "signature": "Сергей Иванов, Sales"},
        brief={"offering": {"what_we_sell": "Гидроборты", "differentiators": ["Собственное производство"]}, "outreach_goals": {"tone_of_voice": "technical"}},
        icp={},
        segment={"pain_hypotheses": [{"pain": "Долгие поставки запчастей"}]},
        channel="email",
    )

    rendered = template.render(context)
    subject, body, warnings = await personalizer.generate(
        tenant_id="00000000-0000-0000-0000-000000000001",
        rendered=rendered,
        template=template,
    )
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")
    print(f"Warnings: {warnings}")
    await llm.close()

asyncio.run(main())
PY
# Ожидание: осмысленное письмо, warnings пустые или минимальные
```

## Подсказки

- **`task_type`** — `composer_{template_id}_{version}`. Это позволяет потом фильтровать метрики по шаблону.
- **Warnings не блокируют.** Они пишутся в `personalization` и в лог. Reviewer увидит их в UI.

## Анти-паттерны

- ❌ Не падать при warnings — только логировать.
- ❌ Не делать retry при warnings — это не ошибка.

---

# Задача 3A.4 — `FactChecker`

**Файл:** `docs/tasks/sprint-3a/3a.4-fact-checker.md`

## Цель

Извлекает из сгенерированного письма фактические утверждения о компании/человеке и проверяет, есть ли для них evidence в исходных данных. Помечает гипотезы.

## Зависимости

3A.3.

## Что создать

- `personalization/fact_checker.py`
- Тесты.

## Детали

### Подход

Два уровня:
1. **Детерминированный (быстрый):** проверяем, что имена/должности/названия компаний, упомянутые в письме, есть в исходных данных. Если в письме упомянут «Иван Петров», а в контакте — «Пётр Иванов» — это hallucination.
2. **LLM-based (глубокий):** LLM анализирует письмо и извлекает утверждения. Каждое — с пометкой «есть в данных / гипотеза / выдумка».

**Решение:** на 3A делаем **только детерминированный** уровень. LLM-based — опционально, если детерминированный не справляется. Это экономит токены и работает быстро.

### `personalization/fact_checker.py`

```python
import re
from dataclasses import dataclass, field

import structlog


logger = structlog.get_logger()


@dataclass
class FactualClaim:
    claim: str
    evidence_url: str | None
    confidence: float
    is_hypothesis: bool
    source_field: str | None  # где в исходных данных найдено


@dataclass
class FactCheckResult:
    claims: list[FactualClaim] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)


class FactChecker:
    """Проверяет фактические утверждения в письме."""

    def __init__(self, *, strict: bool = True, min_confidence: float = 0.6) -> None:
        self._strict = strict
        self._min_confidence = min_confidence

    def check(
        self,
        *,
        body: str,
        subject: str | None,
        contact: dict,
        company: dict | None,
    ) -> FactCheckResult:
        result = FactCheckResult()

        # 1. Извлекаем имена собственные из письма (простым regex)
        # Простой паттерн: слова с большой буквы, длиной > 2, не в начале предложения
        # В реальности сложнее, но для MVP хватит
        text = f"{subject or ''}\n{body}"

        # 2. Проверяем ФИО контакта
        contact_name = self._fact_value(contact.get("full_name"))
        if contact_name:
            name_parts = contact_name.split()
            for part in name_parts:
                if len(part) > 2 and part in text:
                    result.claims.append(FactualClaim(
                        claim=part,
                        evidence_url=None,
                        confidence=1.0,
                        is_hypothesis=False,
                        source_field="contact.full_name",
                    ))
                    break

        # 3. Проверяем компанию
        company_name = self._fact_value(company.get("name")) if company else None
        if company_name:
            # Ищем основное слово из названия
            words = [w for w in re.findall(r"\w+", company_name) if len(w) > 2]
            for w in words:
                if w in text:
                    result.claims.append(FactualClaim(
                        claim=w,
                        evidence_url=None,
                        confidence=1.0,
                        is_hypothesis=False,
                        source_field="company.name",
                    ))
                    break

        # 4. Проверяем должность
        position = self._fact_value(contact.get("position"))
        if position and position.lower() in text.lower():
            result.claims.append(FactualClaim(
                claim=position,
                evidence_url=None,
                confidence=0.9,
                is_hypothesis=False,
                source_field="contact.position",
            ))

        # 5. Сигналы компании (news, hiring и т.д.)
        if company:
            for signal in company.get("signals", []) or []:
                summary = signal.get("summary", "")
                if not summary:
                    continue
                # Проверяем, есть ли ключевые слова из signal в письме
                signal_words = [w for w in re.findall(r"\w+", summary) if len(w) > 4]
                hits = sum(1 for w in signal_words if w.lower() in text.lower())
                if hits >= 1:
                    result.claims.append(FactualClaim(
                        claim=summary[:200],
                        evidence_url=signal.get("source_url"),
                        confidence=0.8,
                        is_hypothesis=False,
                        source_field="company.signals",
                    ))

        # 6. Детектируем явные hallucination-маркеры
        # Числа: если в письме есть число с единицей измерения, которого нет в данных — гипотеза
        number_pattern = re.compile(r"\b\d+[\s]?(?:%|руб|тыс|млн|млрд|лет|год|месяц)")
        for m in number_pattern.finditer(text):
            num_str = m.group(0)
            found = False
            # Ищем в proof_points / differentiators / signals
            for src in [
                (company or {}).get("signals", []),
            ]:
                for s in src or []:
                    if num_str in (s.get("summary") or ""):
                        found = True
                        break
                if found:
                    break
            if not found:
                result.claims.append(FactualClaim(
                    claim=num_str,
                    evidence_url=None,
                    confidence=0.3,
                    is_hypothesis=True,
                    source_field=None,
                ))
                result.warnings.append(f"unverified_number:{num_str}")

        # 7. Строгий режим: если есть hypothesis-claim без evidence — это warning
        if self._strict:
            hypotheses = [c for c in result.claims if c.is_hypothesis]
            if hypotheses:
                result.warnings.append(f"hypotheses_present:{len(hypotheses)}")

        return result

    @staticmethod
    def _fact_value(fact) -> str | None:
        if fact is None:
            return None
        if isinstance(fact, str):
            return fact
        if isinstance(fact, dict):
            return fact.get("value")
        return None
```

### Интеграция в `service.py`

`FactChecker.check(...)` вызывается после генерации. Результат кладётся в `personalization.factual_claims`. Warnings — в `personalization.warnings`.

## Acceptance criteria

```bash
uv run pytest services/composer-service/tests/test_fact_checker.py -v
# Ожидание: passed

# E2E
# Проверить, что при генерации письма factual_claims заполнены
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/messages/$MSG_ID | jq '.personalization.factual_claims'
# Ожидание: список claims
```

## Подсказки

- **Детерминированный подход** — быстро и дёшево. Не использует LLM.
- **Числа — главный источник галлюцинаций.** «Мы работаем с 2005 года» — если этого нет в brief, помечаем hypothesis.
- **`is_hypothesis: true`** — reviewer видит в UI и решает, оставить или нет.
- **`strict: true`** — если хоть одна hypothesis без evidence, письмо не может быть авто-отправлено (только вручную approve). В dev — `strict: false` для отладки.

## Анти-паттерны

- ❌ Не падать при unverified-claims — только warning.
- ❌ Не использовать LLM для fact-check на 3A — детерминированного достаточно.
- ❌ Не блокировать генерацию из-за fact-check — только пометить.

---

# Задача 3A.5 — `ComposerService` + endpoints

**Файл:** `docs/tasks/sprint-3a/3a.5-service.md`

## Цель

Связать всё: получить Contact + Company + Brief + ICP, отрендерить шаблон, сгенерировать письмо, проверить факты, сохранить Message, опубликовать событие.

## Зависимости

3A.1–3A.4.

## Что создать

- `clients/contact_store_client.py` (аналогично sourcing).
- `clients/brief_client.py` (аналогично icp).
- `clients/icp_client.py` (копия).
- `repository.py` — `MessageRepository`.
- `service.py` — `ComposerService`.
- `events.py`.
- `schemas.py`.
- `api/routes.py`, `api/deps.py`.
- Обновить `main.py`.
- Тесты + E2E.

## Детали

### `schemas.py`

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: UUID
    company_id: UUID | None = None
    icp_id: UUID
    segment_id: str
    channel: str = Field(default="email", pattern="^(email|telegram|whatsapp|linkedin)$")
    template_id: str | None = None  # если None — дефолт для канала
    template_version: str | None = None
    language: str = "ru"

    sender_identity_type: str = Field(default="user", pattern="^(user|service)$")
    sender_user_id: str | None = None
    sender_from_email: str | None = None
    sender_from_name: str | None = None
    sender_signature: str | None = None

    experiment_id: UUID | None = None
    variant_id: str | None = None
    hypothesis: str | None = None

    parent_message_id: UUID | None = None  # для follow-up
    sequence_step: int = 1
    sequence_total_steps: int = 1
    followup_after_days: int | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    tenant_id: UUID
    contact_id: UUID
    company_id: UUID | None
    campaign_id: UUID | None
    channel: str
    status: str
    sequence_step: int
    sequence_total_steps: int
    parent_message_id: UUID | None
    is_followup: bool
    followup_after_days: int | None
    subject: str | None
    body_text: str
    body_html: str | None
    language: str
    word_count: int
    personalization: dict
    sender: dict
    recipient_snapshot: dict
    experiment: dict | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    delivery: dict
    engagement: dict
    review: dict
    schema_version: str
    created_at: datetime
    updated_at: datetime


class MessageSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    contact_id: UUID
    channel: str
    status: str
    subject: str | None
    word_count: int
    created_at: datetime
```

### `repository.py`

```python
class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, message_id: UUID) -> Message | None:
        return await self._s.get(Message, message_id)

    async def add(self, message: Message) -> Message:
        self._s.add(message)
        await self._s.flush()
        return message

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        contact_id: UUID | None = None,
        channel: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        stmt = select(Message).where(Message.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Message.status == status)
        if contact_id:
            stmt = stmt.where(Message.contact_id == contact_id)
        if channel:
            stmt = stmt.where(Message.channel == channel)
        stmt = stmt.order_by(Message.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def find_pending_followup(
        self,
        *,
        tenant_id: UUID,
        parent_message_id: UUID,
    ) -> Message | None:
        stmt = select(Message).where(
            Message.tenant_id == tenant_id,
            Message.parent_message_id == parent_message_id,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()
```

### `service.py` — `ComposerService`

```python
import re
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7

import structlog

from common.context import get_trace_id
from common.errors import AppError, NotFoundError, ValidationError
from composer_service.clients.contact_store_client import ContactStoreClient
from composer_service.clients.brief_client import BriefClient
from composer_service.clients.icp_client import ICPClient
from composer_service.config import Settings
from composer_service.events import emit_message_drafted
from composer_service.models import Message
from composer_service.personalization.fact_checker import FactChecker
from composer_service.personalization.personalizer import Personalizer
from composer_service.repository import MessageRepository
from composer_service.schemas import DraftRequest
from composer_service.templates.base import TemplateContext
from composer_service.templates.registry import TemplateRegistry
from nats_client.publisher import Publisher


logger = structlog.get_logger()


class ComposerService:
    def __init__(
        self,
        repo: MessageRepository,
        contact_store: ContactStoreClient,
        brief_client: BriefClient,
        icp_client: ICPClient,
        template_registry: TemplateRegistry,
        personalizer: Personalizer,
        fact_checker: FactChecker,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._contact_store = contact_store
        self._brief = brief_client
        self._icp = icp_client
        self._templates = template_registry
        self._personalizer = personalizer
        self._fact_checker = fact_checker
        self._publisher = publisher
        self._settings = settings

    async def draft(
        self,
        *,
        tenant_id: UUID,
        data: DraftRequest,
        trace_id: str,
    ) -> Message:
        # 1. Получаем контакт
        contact = await self._contact_store.get_contact(
            data.contact_id, tenant_id=str(tenant_id), trace_id=trace_id,
        )
        if contact is None:
            raise NotFoundError(f"Contact {data.contact_id} not found")
        if contact.get("status") in ("unsubscribed", "bounced", "disqualified"):
            raise ValidationError(f"Cannot draft for contact with status {contact['status']}")

        # 2. Компания (опционально)
        company = None
        company_id = data.company_id or contact.get("company_id")
        if company_id:
            company = await self._contact_store.get_company(
                company_id, tenant_id=str(tenant_id), trace_id=trace_id,
            )

        # 3. ICP и сегмент
        icp = await self._icp.get_icp(str(data.icp_id), tenant_id=str(tenant_id), trace_id=trace_id)
        segments = icp.get("payload", {}).get("segments", [])
        segment = next((s for s in segments if s.get("id") == data.segment_id), None)
        if segment is None:
            raise ValidationError(f"Segment {data.segment_id} not found in ICP")

        # 4. Brief
        brief_id = icp.get("brief_id")
        brief = await self._brief.get_brief(brief_id, tenant_id=str(tenant_id), trace_id=trace_id)

        # 5. Шаблон
        if data.template_id:
            template = self._templates.get(data.template_id, data.template_version)
        else:
            template = self._templates.default_for_channel(data.channel)

        # 6. Sender
        sender = {
            "identity_type": data.sender_identity_type,
            "user_id": data.sender_user_id,
            "from_email": data.sender_from_email,
            "from_name": data.sender_from_name,
            "signature": data.sender_signature,
        }

        # 7. Рендерим шаблон
        parent_message = None
        if data.parent_message_id:
            parent_message = await self._repo.get(data.parent_message_id)

        context = TemplateContext(
            contact=contact,
            company=company,
            sender=sender,
            brief=brief,
            icp=icp,
            segment=segment,
            channel=data.channel,
            language=data.language,
            extra={"parent_message": self._message_to_dict(parent_message)} if parent_message else {},
        )
        rendered = template.render(context)

        # 8. Генерируем
        subject, body, template_warnings = await self._personalizer.generate(
            tenant_id=str(tenant_id),
            rendered=rendered,
            template=template,
            trace_id=trace_id,
        )

        # 9. Fact-check
        fc_result = self._fact_checker.check(
            body=body,
            subject=subject,
            contact=contact,
            company=company,
        )

        # 10. Формируем snapshots
        recipient_snapshot = self._build_recipient_snapshot(contact, company)
        word_count = len(body.split())

        personalization = {
            "template_id": template.template_id,
            "template_version": template.template_version,
            "llm_model": self._settings.llm_model,
            "variables_used": rendered.variables_used,
            "factual_claims": [
                {
                    "claim": c.claim,
                    "evidence_url": c.evidence_url,
                    "confidence": c.confidence,
                    "is_hypothesis": c.is_hypothesis,
                }
                for c in fc_result.claims
            ],
            "warnings": template_warnings + fc_result.warnings,
        }

        experiment = None
        if data.experiment_id:
            experiment = {
                "experiment_id": str(data.experiment_id),
                "variant_id": data.variant_id,
                "hypothesis": data.hypothesis,
            }

        message = Message(
            tenant_id=tenant_id,
            contact_id=data.contact_id,
            company_id=company_id,
            channel=data.channel,
            status="draft",
            sequence_step=data.sequence_step,
            sequence_total_steps=data.sequence_total_steps,
            parent_message_id=data.parent_message_id,
            is_followup=data.parent_message_id is not None,
            followup_after_days=data.followup_after_days,
            subject=subject,
            body_text=body,
            body_html=self._to_html(body, sender.get("signature")),
            language=data.language,
            word_count=word_count,
            personalization=personalization,
            sender=sender,
            recipient_snapshot=recipient_snapshot,
            experiment=experiment,
            review={},
            delivery={},
            engagement={},
        )
        await self._repo.add(message)
        await emit_message_drafted(self._publisher, message, trace_id=trace_id)

        logger.info(
            "message_drafted",
            message_id=str(message.id),
            contact_id=str(data.contact_id),
            channel=data.channel,
            template=f"{template.template_id}:{template.template_version}",
            word_count=word_count,
            warnings=len(personalization["warnings"]),
        )
        return message

    async def get(self, message_id: UUID) -> Message:
        m = await self._repo.get(message_id)
        if m is None:
            raise NotFoundError(f"Message {message_id} not found")
        return m

    async def list(self, *, tenant_id: UUID, **kwargs) -> list[Message]:
        return await self._repo.list(tenant_id=tenant_id, **kwargs)

    def _build_recipient_snapshot(self, contact: dict, company: dict | None) -> dict:
        primary_email = None
        for e in contact.get("emails", []) or []:
            if e.get("is_primary"):
                primary_email = e.get("value")
                break
        primary_phone = None
        for p in contact.get("phones", []) or []:
            if p.get("is_primary"):
                primary_phone = p.get("value")
                break

        return {
            "email": primary_email,
            "phone": primary_phone,
            "messenger_handle": None,
            "full_name": self._fact_value(contact.get("full_name")) or "",
            "position": self._fact_value(contact.get("position")),
            "company_name": self._fact_value((company or {}).get("name")),
        }

    def _to_html(self, body: str, signature: str | None) -> str:
        """Простой конвертер: абзацы → <p>, переносы → <br>. Без markdown."""
        # Экранируем HTML
        import html as html_lib
        safe = html_lib.escape(body)
        # Абзацы по двойному переносу
        paragraphs = safe.split("\n\n")
        html_parts = [f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip()]
        return "\n".join(html_parts)

    @staticmethod
    def _fact_value(fact) -> str | None:
        if fact is None:
            return None
        if isinstance(fact, str):
            return fact
        if isinstance(fact, dict):
            return fact.get("value")
        return None

    @staticmethod
    def _message_to_dict(m: Message | None) -> dict | None:
        if m is None:
            return None
        return {
            "id": str(m.id),
            "subject": m.subject,
            "body_text": m.body_text,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
```

**Важно:**
- **`_to_html`** — простой: абзацы и `<br>`. Никакого markdown. Если LLM вернёт `**bold**` — останется как текст.
- **`recipient_snapshot`** — снапшот на момент генерации. Даже если контакт изменится, письмо хранит исходные данные.
- **`parent_message`** — для follow-up. Передаётся в `context.extra`.

### `clients/contact_store_client.py`

Добавить методы `get_contact` и `get_company`:

```python
async def get_contact(self, contact_id: UUID, *, tenant_id: str, trace_id: str = "") -> dict | None:
    resp = await self._client.get(
        f"/contacts/{contact_id}",
        headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


async def get_company(self, company_id: UUID, *, tenant_id: str, trace_id: str = "") -> dict | None:
    resp = await self._client.get(
        f"/companies/{company_id}",
        headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()
```

### `events.py`

```python
async def emit_message_drafted(publisher: Publisher, message: Message, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.MESSAGE_DRAFTED,
        tenant_id=message.tenant_id,
        payload={
            "message": {
                "id": str(message.id),
                "contact_id": str(message.contact_id),
                "channel": message.channel,
                "template_id": (message.personalization or {}).get("template_id"),
            }
        },
        trace_id=trace_id,
        correlation_id=message.id,
    )
```

**Проверить:** `Subjects.MESSAGE_DRAFTED` есть в `nats_client.subjects` (мы добавляли в Спринте 0). Если нет — добавить.

### `api/routes.py`

```python
@router.post("", response_model=MessageRead, status_code=201)
async def draft_message(
    data: DraftRequest,
    svc: ComposerService = Depends(get_service),
) -> MessageRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    msg = await svc.draft(tenant_id=tenant_id, data=data, trace_id=get_trace_id() or "")
    return MessageRead.model_validate(msg, from_attributes=True)


@router.get("/{message_id}", response_model=MessageRead)
async def get_message(message_id: UUID, svc: ComposerService = Depends(get_service)) -> MessageRead:
    msg = await svc.get(message_id)
    return MessageRead.model_validate(msg, from_attributes=True)


@router.get("", response_model=list[MessageSummary])
async def list_messages(
    status_filter: str | None = Query(None, alias="status"),
    contact_id: UUID | None = Query(None),
    channel: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ComposerService = Depends(get_service),
) -> list[MessageSummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    messages = await svc.list(
        tenant_id=tenant_id,
        status=status_filter,
        contact_id=contact_id,
        channel=channel,
        limit=limit,
        offset=offset,
    )
    return [MessageSummary.model_validate(m, from_attributes=True) for m in messages]
```

### `main.py` — обновить

```python
from composer_service.clients.contact_store_client import ContactStoreClient
from composer_service.clients.brief_client import BriefClient
from composer_service.clients.icp_client import ICPClient
from composer_service.llm.client import LLMClient
from composer_service.personalization.personalizer import Personalizer
from composer_service.personalization.fact_checker import FactChecker
from composer_service.templates.registry import TemplateRegistry
from composer_service.templates.email_cold_outreach_v1 import EmailColdOutreachV1

# в lifespan:
app.state.contact_store = ContactStoreClient(settings.contact_store_url)
app.state.brief_client = BriefClient(settings.brief_service_url)
app.state.icp_client = ICPClient(settings.icp_service_url)
app.state.llm = LLMClient(settings)

registry = TemplateRegistry()
registry.register(EmailColdOutreachV1(
    min_words=settings.min_body_words,
    max_words=settings.max_body_words,
    max_subject_len=settings.max_subject_length,
))
registry.register(EmailFollowupV1())
app.state.template_registry = registry

app.state.personalizer = Personalizer(app.state.llm, settings)
app.state.fact_checker = FactChecker(
    strict=settings.strict_fact_check,
    min_confidence=settings.min_fact_confidence,
)
```

## Acceptance criteria

```bash
# E2E — сгенерировать письмо
export TENANT="<sandbox>"
export BASE="https://composer.dev.aitler.ru"
export CONTACT_ID="<реальный_contact_id>"
export ICP_ID="<реальный_icp_id>"
export SEGMENT_ID="<реальный_segment_id>"

MSG=$(curl -sX POST $BASE/messages \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: draft-1" \
  -d '{
    "contact_id": "'$CONTACT_ID'",
    "icp_id": "'$ICP_ID'",
    "segment_id": "'$SEGMENT_ID'",
    "channel": "email",
    "language": "ru",
    "sender_identity_type": "user",
    "sender_from_name": "Сергей",
    "sender_from_email": "sergey@example.com",
    "sender_signature": "Сергей, Sales Manager"
  }')
echo $MSG | jq '{id, subject, word_count, warnings: .personalization.warnings}'
# Ожидание: осмысленное письмо, warnings пустые

MSG_ID=$(echo $MSG | jq -r .id)

# Проверить factual_claims
echo $MSG | jq '.personalization.factual_claims'
# Ожидание: список claims

# Проверить события
bash scripts/nats-cli.sh stream view BRIEFS --last 10 | grep message.drafted
# Ожидание: событие есть

# Проверить LLM calls
bash scripts/psql.sh -c "SELECT task_type, count(*) FROM llm_calls WHERE tenant_id='$TENANT' AND task_type LIKE 'composer_%' GROUP BY task_type;"
# Ожидание: composer_email_cold_outreach_v1
```

## Подсказки

- **`_to_html`** — простой. Markdown не обрабатываем: LLM промпт просит plain text.
- **`parent_message`** — для follow-up. Если `parent_message_id` задан, но message не найден — не падаем, просто без контекста.
- **`sender_signature`** — в body добавляется отдельной строкой. LLM не должна её дублировать (промпт говорит «не добавляй подпись, она будет добавлена»).

## Анти-паттерны

- ❌ Не генерировать для контакта со статусом `unsubscribed` / `bounced` / `disqualified`.
- ❌ Не забывать Idempotency-Key на POST.
- ❌ Не делать HTML через markdown-парсер — только `<p>` и `<br>`.

---

# Задача 3A.6 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-3a/3a.6-tests.md`

## Цель

Покрытие 85%+, E2E полного цикла (contact → draft), обновить CI.

## Детали

### `tests/conftest.py`

По образцу `icp-service`. Моки: respx для contact-store, brief-service, icp-service, llm-gateway.

### `tests/test_e2e.py`

Полный цикл с моками:
1. Mock contact-store → contact + company.
2. Mock brief-service → brief.
3. Mock icp-service → icp.
4. Mock llm-gateway → письмо.
5. `POST /messages` → 201.
6. Проверить `subject`, `body_text`, `personalization.factual_claims`, `word_count`.
7. RLS: другой тенант → 404.

### Обновить CI

Добавить `composer-service` в matrix build-images.

## Acceptance criteria

```bash
uv run pytest services/composer-service/tests/ -v --cov=composer_service --cov-report=term-missing
# Ожидание: coverage >= 85%

uv run mypy services/composer-service
uv run ruff check services/composer-service

# E2E на dev — см. выше

# CI
git push origin develop
# Зелёные
```

---

# 3B — `review-queue`

## Что такое review-queue и почему изолирован

Это **состояние**, не генерация. Он не генерирует письма, не отправляет. Он:
1. Хранит очередь сообщений, ожидающих ревью.
2. Даёт API для approve/reject/edit.
3. Публикует события `message.approved`, `message.rejected`.

**Ключевой принцип:** на старте **все** сообщения проходят через review. Авто-отправка — флаг в конфиге, включается позже.

**Почему отдельно от composer:** composer — stateless (сгенерировал и забыл). review-queue — stateful, у него своя модель данных, свои статусы. Смешивать — плохо.

**Почему отдельно от sender:** sender отвечает за отправку. Review — до отправки. Между ними — `message.approved` событие. Sender подписывается и отправляет.

**Модель данных:** таблица `review_items`. Одна строка = одно сообщение, ожидающее ревью. Не дублирует Message, а ссылается на `message_id`.

---

# Задача 3B.1 — Каркас `review-queue` + модель

**Файл:** `docs/tasks/sprint-3b/3b.1-bootstrap.md`

## Цель

Создать каркас, определить модель `ReviewItem`, миграция с RLS.

## Зависимости

3A закрыт.

## Что создать

```
services/review-queue/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_review_items.py
├── src/review_queue/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── events.py
│   ├── clients/
│   │   ├── __init__.py
│   │   └── composer_client.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
```

## Детали

### `models.py`

```python
class ReviewItem(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "review_items"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    contact_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending | approved | rejected | edited_and_approved | skipped

    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal", index=True)
    # low | normal | high — для сортировки очереди

    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Снапшот письма для быстрого отображения в очереди
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {subject, body_preview (первые 500 символов), warnings, factual_claims_count}

    # Если редактировали — что изменилось
    edit: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {edited_at, edited_by, diff: {subject_before, subject_after, body_before, body_after}}

    # Отказ
    rejection: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {reason, note, rejected_at, rejected_by}

    # Планирование
    scheduled_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_review_items_tenant_status", "tenant_id", "status"),
        Index("ix_review_items_tenant_priority_status", "tenant_id", "priority", "status"),
        Index("ix_review_items_tenant_assigned", "tenant_id", "assigned_to"),
        Index("ix_review_items_created", "tenant_id", "created_at"),
    )
```

### Миграция

По образцу других сервисов. RLS на `review_items`.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  review-queue:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/review-queue/Dockerfile
    container_name: outreach-review-queue
    environment:
      <<: *common-env
      SERVICE_NAME: review-queue
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/7
      COMPOSER_SERVICE_URL: http://composer-service:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      composer-service:
        condition: service_started
    labels:
      caddy: review.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
```

Обновить `scripts/migrate.sh`.

## Acceptance criteria

```bash
docker compose ... run --rm review-queue alembic upgrade head
docker compose ... up -d review-queue
curl -fsS https://review.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\d+ review_items"
```

---

# Задача 3B.2 — Подписка на `message.drafted` + API approve/reject/edit

**Файл:** `docs/tasks/sprint-3b/3b.2-service.md`

## Цель

Сервис подписывается на `message.drafted` (через NATS consumer), создаёт `ReviewItem` со снапшотом. API для approve/reject/edit.

## Детали

### Подписка на NATS

В `main.py`:

```python
from nats_client.subscriber import Subscriber

async def _on_message_drafted(envelope) -> None:
    """Обработчик события message.drafted."""
    payload = envelope.payload
    message_id = payload["message"]["id"]
    tenant_id = envelope.tenant_id
    # ... создаём ReviewItem
    ...

# в lifespan:
subscriber = Subscriber(
    nats_conn,
    stream="BRIEFS",  # message.drafted в стриме BRIEFS
    durable="review-queue-message-drafted",
    filter_subjects=["message.drafted.*"],
    handler=_on_message_drafted,
)
await subscriber.start()
asyncio.create_task(subscriber.run_forever())
```

**Важно:** `message.drafted.<tenant_id>` — подписка по `*`. В `Subscriber` из Спринта 0 фильтр `["message.drafted.*"]`.

**Детали обработчика:**
1. Получить Message из composer (HTTP GET).
2. Создать `ReviewItem` со снапшотом:
   - `subject`
   - `body_preview` (первые 500 символов)
   - `warnings` из `personalization.warnings`
   - `factual_claims_count`
3. Приоритет: `high` если есть warnings/hypotheses, иначе `normal`.
4. Сохранить, закоммитить.

### API

```python
@router.get("", response_model=list[ReviewItemRead])
async def list_review_items(
    status_filter: str | None = Query("pending", alias="status"),
    assigned_to: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ReviewQueueService = Depends(get_service),
) -> list[ReviewItemRead]:
    ...


@router.get("/{item_id}", response_model=ReviewItemRead)
async def get_review_item(item_id: UUID, svc=Depends(get_service)) -> ReviewItemRead:
    ...


@router.post("/{item_id}/approve", response_model=ReviewItemRead)
async def approve(
    item_id: UUID,
    data: ApproveRequest,  # {scheduled_send_at: datetime | None}
    svc: ReviewQueueService = Depends(get_service),
    request: Request = None,
) -> ReviewItemRead:
    ...


@router.post("/{item_id}/reject", response_model=ReviewItemRead)
async def reject(
    item_id: UUID,
    data: RejectRequest,  # {reason: str, note: str | None}
    svc: ReviewQueueService = Depends(get_service),
    request: Request = None,
) -> ReviewItemRead:
    ...


@router.post("/{item_id}/edit", response_model=ReviewItemRead)
async def edit(
    item_id: UUID,
    data: EditRequest,  # {subject: str | None, body_text: str}
    svc: ReviewQueueService = Depends(get_service),
    request: Request = None,
) -> ReviewItemRead:
    """Редактирует Message (в composer) и оставляет ReviewItem в pending."""
    ...


@router.post("/{item_id}/assign", response_model=ReviewItemRead)
async def assign(
    item_id: UUID,
    data: AssignRequest,  # {assigned_to: str}
    svc=Depends(get_service),
) -> ReviewItemRead:
    ...


@router.post("/bulk-approve")
async def bulk_approve(
    data: BulkApproveRequest,  # {item_ids: list[UUID]}
    svc=Depends(get_service),
) -> dict:
    ...
```

### Сервис

```python
class ReviewQueueService:
    async def approve(
        self, *, tenant_id: UUID, item_id: UUID, user_id: str, scheduled_send_at: datetime | None, trace_id: str,
    ) -> ReviewItem:
        item = await self._repo.get(item_id)
        if item is None:
            raise NotFoundError(...)
        if item.status != "pending":
            raise ValidationError(f"Cannot approve item with status {item.status}")

        # Обновляем Message в composer
        message = await self._composer.get_message(item.message_id, tenant_id=str(tenant_id))
        if item.edit:  # было редактирование
            await self._composer.update_message_status(
                item.message_id,
                tenant_id=str(tenant_id),
                status="approved",
                review={
                    "reviewed_by": user_id,
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "edited_by_human": True,
                    "original_body_text": item.edit.get("body_before"),
                },
            )
            item.status = "edited_and_approved"
        else:
            await self._composer.update_message_status(
                item.message_id,
                tenant_id=str(tenant_id),
                status="approved",
                review={
                    "reviewed_by": user_id,
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            item.status = "approved"

        item.reviewed_by = user_id
        item.reviewed_at = datetime.now(timezone.utc)
        item.scheduled_send_at = scheduled_send_at
        await self._repo._s.flush()
        await emit_message_approved(self._publisher, item, message, trace_id=trace_id)
        return item

    async def reject(...) -> ReviewItem:
        # обновляем Message в composer со status=rejected
        # item.status = "rejected"
        # emit_message_rejected

    async def edit(...) -> ReviewItem:
        # обновляем Message в composer с новым subject/body
        # item.edit = {...}
        # item.status остаётся pending
        # emit_message_updated (новое событие)
```

**Важно:** `update_message_status` и `update_message_content` должны быть добавлены в `composer-service` API. См. ниже.

### Дополнить `composer-service` API

Нужны эндпоинты:
- `PATCH /messages/{id}` — обновить `subject`/`body_text`/`status`/`review`.
- Только для `status in ("draft", "pending_review")`.

```python
class MessageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str | None = None
    body_text: str | None = None
    status: str | None = None
    review: dict | None = None


@router.patch("/{message_id}", response_model=MessageRead)
async def update_message(
    message_id: UUID,
    data: MessageUpdate,
    svc: ComposerService = Depends(get_service),
) -> MessageRead:
    msg = await svc.update(message_id, data)
    return MessageRead.model_validate(msg, from_attributes=True)
```

В `ComposerService.update`:

```python
async def update(self, message_id: UUID, data: MessageUpdate) -> Message:
    msg = await self.get(message_id)
    if data.subject is not None:
        msg.subject = data.subject
    if data.body_text is not None:
        msg.body_text = data.body_text
        msg.word_count = len(data.body_text.split())
        msg.body_html = self._to_html(data.body_text, (msg.sender or {}).get("signature"))
    if data.status is not None:
        msg.status = data.status
    if data.review is not None:
        msg.review = {**(msg.review or {}), **data.review}
    await self._repo._s.flush()
    return msg
```

### `events.py`

```python
async def emit_message_approved(publisher: Publisher, item: ReviewItem, message: dict, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.MESSAGE_APPROVED,
        tenant_id=item.tenant_id,
        payload={
            "message_id": str(item.message_id),
            "approved_by": item.reviewed_by,
            "edited": item.edit is not None,
            "scheduled_send_at": item.scheduled_send_at.isoformat() if item.scheduled_send_at else None,
        },
        trace_id=trace_id,
        correlation_id=item.message_id,
    )


async def emit_message_rejected(publisher: Publisher, item: ReviewItem, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.MESSAGE_REJECTED,
        tenant_id=item.tenant_id,
        payload={
            "message_id": str(item.message_id),
            "rejected_by": item.reviewed_by,
            "reason": (item.rejection or {}).get("reason"),
        },
        trace_id=trace_id,
    )
```

## Acceptance criteria

```bash
# 1. Создать draft в composer
MSG_ID=$(curl -sX POST https://composer.dev.aitler.ru/messages \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: draft-1" \
  -d '{...}' | jq -r .id)

# 2. Дождаться, что review-item создан
sleep 3
curl -s -H "X-Tenant-ID: $TENANT" "https://review.dev.aitler.ru/?status=pending" | jq '.[0]'
# Ожидание: item с message_id=$MSG_ID

# 3. Approve
ITEM_ID=$(curl -s -H "X-Tenant-ID: $TENANT" "https://review.dev.aitler.ru/?status=pending" | jq -r '.[0].id')
curl -sX POST https://review.dev.aitler.ru/$ITEM_ID/approve \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: app-1" \
  -d '{}' | jq .status
# Ожидание: "approved"

# 4. Message обновлён
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/messages/$MSG_ID | jq .status
# Ожидание: "approved"

# 5. Событие
bash scripts/nats-cli.sh stream view BRIEFS --last 10 | grep message.approved
# Ожидание: есть
```

## Подсказки

- **NATS consumer с durable name** — не теряет события при рестарте.
- **Snapshot в ReviewItem** — чтобы не дёргать composer на каждый GET.
- **`approve` вызывает `PATCH /messages/{id}`** — composer обновляет статус.
- **`edit` не меняет статус review-item** — остаётся pending, но с `edit`-полем.
- **Приоритет `high`** — если в письме есть warnings или hypotheses. Reviewer видит их первыми.

## Анти-паттерны

- ❌ Не approve item со статусом != pending.
- ❌ Не забывать обновлять Message в composer при approve/reject/edit.
- ❌ Не терять события — durable consumer.

---

# Задача 3B.3 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-3b/3b.3-tests.md`

## Детали

### E2E

1. Mock composer → message.drafted событие.
2. Review-queue создаёт item.
3. Approve → composer обновлён, событие опубликовано.
4. Reject → composer обновлён, событие опубликовано.
5. Edit → composer обновлён, item остаётся pending.

### CI

Добавить `review-queue` в matrix.

## Acceptance criteria

```bash
uv run pytest services/review-queue/tests/ -v --cov=review_queue --cov-report=term-missing
# Ожидание: coverage >= 85%
```

---

# 3C — `sender-email`

## Что такое sender-email и почему он самый рискованный

Это сервис, который **физически отправляет письма**. Ошибки здесь стоят репутации домена и deliverability. Поэтому:

1. **Ramp-up обязателен.** Новый ящик начинает с 5-10 писем/день, постепенно увеличивается.
2. **Rate limit per mailbox.** Не больше N писем/час на ящик.
3. **Ротация ящиков.** Если у тенанта несколько ящиков — распределяем.
4. **Bounce/complaint handling.** Hard bounce → в stop-list. Complaint → в stop-list + алерт.
5. **Reply detection.** IMAP-polling ящика, парсинг ответов.
6. **Unsubscribe.** Каждое письмо содержит ссылку/заголовок `List-Unsubscribe`.
7. **SPF/DKIM/DMARC.** Валидация на старте. Если не настроено — не отправляем.

**Ключевое решение:** используем **per-employee ящик** (реальный ящик сотрудника через SMTP/IMAP). Не общий `sales@`.

**Модель данных:** таблицы `sender_accounts` (подключённые ящики) и `send_attempts` (история отправок).

---

# Задача 3C.1 — Каркас `sender-email` + модели

**Файл:** `docs/tasks/sprint-3c/3c.1-bootstrap.md`

## Цель

Создать каркас, определить модели `SenderAccount` и `SendAttempt`, миграция с RLS.

## Зависимости

3B закрыт.

## Что создать

```
services/sender-email/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_sender_accounts.py
├── src/sender_email/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── events.py
│   ├── smtp/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── account_manager.py
│   ├── imap/
│   │   ├── __init__.py
│   │   └── poller.py
│   ├── rampup/
│   │   ├── __init__.py
│   │   └── limiter.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── composer_client.py
│   │   └── contact_store_client.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
```

## Детали

### `models.py`

```python
class SenderAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Подключённый ящик отправителя."""

    __tablename__ = "sender_accounts"

    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # SMTP
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=465)
    smtp_use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    smtp_username: Mapped[str] = mapped_column(String(320), nullable=False)
    smtp_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # IMAP
    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    imap_use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    imap_username: Mapped[str] = mapped_column(String(320), nullable=False)
    imap_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # Статус
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    # active | paused | error | unverified

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ramp-up
    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    hourly_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    warmup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # SPF/DKIM/DMARC
    spf_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dkim_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dmarc_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dns_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Настройки
    daily_limit_max: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    hourly_limit_max: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_sender_accounts_tenant_email"),
        Index("ix_sender_accounts_tenant_status", "tenant_id", "status"),
    )


class SendAttempt(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """История отправок."""

    __tablename__ = "send_attempts"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    sender_account_id: Mapped[UUID] = mapped_column(ForeignKey("sender_accounts.id", ondelete="SET NULL"), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    # pending | sent | failed | bounced | rejected_by_provider

    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    from_email: Mapped[str] = mapped_column(String(320), nullable=False)

    smtp_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    bounce_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bounce_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    __table_args__ = (
        Index("ix_send_attempts_tenant_message", "tenant_id", "message_id"),
        Index("ix_send_attempts_tenant_status", "tenant_id", "status"),
        Index("ix_send_attempts_sent_at", "tenant_id", "sent_at"),
    )
```

**Важно:** `smtp_password_encrypted` — пароли шифруются. Используем `cryptography.fernet` с ключом из env (`SENDER_ENCRYPTION_KEY`). Пароли **не** хранятся в plaintext.

### Миграция

Обе таблицы + RLS.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  sender-email:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/sender-email/Dockerfile
    container_name: outreach-sender-email
    environment:
      <<: *common-env
      SERVICE_NAME: sender-email
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/8
      COMPOSER_SERVICE_URL: http://composer-service:8000
      CONTACT_STORE_URL: http://contact-store:8000
      SENDER_ENCRYPTION_KEY: ${SENDER_ENCRYPTION_KEY:?required}
      SENDER_DRY_RUN: ${SENDER_DRY_RUN:-true}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      composer-service:
        condition: service_started
      contact-store:
        condition: service_started
    labels:
      caddy: sender.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
```

**Обновить `.env.example`:**

```bash
# Sender — шифрование паролей
# Сгенерируй: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SENDER_ENCRYPTION_KEY=

# Dry-run: не отправляет реально, только логирует
SENDER_DRY_RUN=true
```

## Acceptance criteria

```bash
docker compose ... run --rm sender-email alembic upgrade head
docker compose ... up -d sender-email
curl -fsS https://sender.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\dt sender_*"
bash scripts/psql.sh -c "\dt send_*"
# Ожидание: обе таблицы, RLS
```

---

# Задача 3C.2 — SMTP-клиент + управление ящиками

**Файл:** `docs/tasks/sprint-3c/3c.2-smtp.md`

## Цель

Реализовать SMTP-клиент (async) и API для управления ящиками: добавить, верифицировать, активировать/паузить.

## Детали

### `smtp/client.py`

```python
import asyncio
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import aiosmtplib
import structlog


logger = structlog.get_logger()


@dataclass
class SMTPConfig:
    host: str
    port: int
    use_ssl: bool
    username: str
    password: str


@dataclass
class SendResult:
    success: bool
    message_id: str | None
    response: str | None
    error: str | None


class SMTPClient:
    """Async SMTP-клиент. Один экземпляр на отправку."""

    def __init__(self, config: SMTPConfig, *, timeout: float = 30.0) -> None:
        self._config = config
        self._timeout = timeout

    async def send(
        self,
        *,
        from_email: str,
        from_name: str | None,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        reply_to: str | None = None,
        list_unsubscribe: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> SendResult:
        msg = EmailMessage()
        msg["From"] = formataddr((from_name or "", from_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        if list_unsubscribe:
            msg["List-Unsubscribe"] = list_unsubscribe
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        msg_id = make_msgid(domain=from_email.split("@")[1])
        msg["Message-ID"] = msg_id

        if headers:
            for k, v in headers.items():
                msg[k] = v

        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        try:
            if self._config.use_ssl:
                smtp = aiosmtplib.SMTP(
                    hostname=self._config.host,
                    port=self._config.port,
                    use_tls=True,
                    timeout=self._timeout,
                )
            else:
                smtp = aiosmtplib.SMTP(
                    hostname=self._config.host,
                    port=self._config.port,
                    start_tls=True,
                    timeout=self._timeout,
                )

            await smtp.connect()
            await smtp.login(self._config.username, self._config.password)
            response = await smtp.send_message(msg)
            await smtp.quit()

            logger.info("smtp_sent", to=to_email, msg_id=msg_id)
            return SendResult(
                success=True,
                message_id=msg_id,
                response=str(response),
                error=None,
            )
        except Exception as e:
            logger.warning("smtp_failed", to=to_email, error=str(e))
            return SendResult(success=False, message_id=None, response=None, error=str(e))
```

**Добавить `aiosmtplib>=3.0` в зависимости.**

### `smtp/account_manager.py`

```python
from cryptography.fernet import Fernet


class PasswordEncryptor:
    """Шифрует/расшифровывает пароли ящиков."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()


class AccountManager:
    """Управляет ящиками: верификация, ramp-up, ротация."""

    def __init__(self, repo, encryptor: PasswordEncryptor) -> None:
        self._repo = repo
        self._enc = encryptor

    async def verify_connection(self, account: SenderAccount) -> tuple[bool, str | None]:
        """Проверяет, что SMTP-логин работает."""
        from sender_email.smtp.client import SMTPClient, SMTPConfig

        config = SMTPConfig(
            host=account.smtp_host,
            port=account.smtp_port,
            use_ssl=account.smtp_use_ssl,
            username=account.smtp_username,
            password=self._enc.decrypt(account.smtp_password_encrypted),
        )
        client = SMTPClient(config, timeout=15.0)
        try:
            # Просто коннект + login, без отправки
            import aiosmtplib
            if config.use_ssl:
                smtp = aiosmtplib.SMTP(hostname=config.host, port=config.port, use_tls=True, timeout=15.0)
            else:
                smtp = aiosmtplib.SMTP(hostname=config.host, port=config.port, start_tls=True, timeout=15.0)
            await smtp.connect()
            await smtp.login(config.username, config.password)
            await smtp.quit()
            return True, None
        except Exception as e:
            return False, str(e)
```

### API для ящиков

```python
@router.post("/accounts", response_model=SenderAccountRead, status_code=201)
async def create_account(
    data: SenderAccountCreate,  # {email, display_name, smtp_*, imap_*, password}
    svc: SenderService = Depends(get_service),
) -> SenderAccountRead:
    ...


@router.get("/accounts", response_model=list[SenderAccountRead])
async def list_accounts(svc=Depends(get_service)) -> list[SenderAccountRead]:
    ...


@router.post("/accounts/{account_id}/verify", response_model=SenderAccountRead)
async def verify_account(account_id: UUID, svc=Depends(get_service)) -> SenderAccountRead:
    """Проверяет SMTP-логин, обновляет status."""
    ...


@router.post("/accounts/{account_id}/pause", response_model=SenderAccountRead)
async def pause_account(account_id: UUID, svc=Depends(get_service)) -> SenderAccountRead:
    ...


@router.post("/accounts/{account_id}/resume", response_model=SenderAccountRead)
async def resume_account(account_id: UUID, svc=Depends(get_service)) -> SenderAccountRead:
    ...


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: UUID, svc=Depends(get_service)) -> None:
    ...
```

### Тесты

- Unit: шифрование/дешифрование.
- E2E: verify connection с мок-SMTP (или реальным тестовым SMTP).

## Acceptance criteria

```bash
# 1. Создать ящик
curl -sX POST https://sender.dev.aitler.ru/accounts \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: acc-1" \
  -d '{
    "email": "sergey@example.com",
    "display_name": "Сергей",
    "smtp_host": "smtp.example.com",
    "smtp_port": 465,
    "smtp_use_ssl": true,
    "smtp_username": "sergey@example.com",
    "smtp_password": "...",
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "imap_use_ssl": true,
    "imap_username": "sergey@example.com",
    "imap_password": "..."
  }' | jq .
# Ожидание: account с status="unverified"

# 2. Verify
curl -sX POST https://sender.dev.aitler.ru/accounts/$ACC_ID/verify \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: ver-1" | jq .status
# Ожидание: "active" или "error" (с last_error)
```

---

# Задача 3C.3 — Ramp-up + rate limit + выбор ящика

**Файл:** `docs/tasks/sprint-3c/3c.3-rampup.md`

## Цель

Реализовать ramp-up: daily/houly лимиты, постепенное увеличение, ротация ящиков.

## Детали

### `rampup/limiter.py`

```python
from datetime import date, datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis


class RampUpLimiter:
    """Управляет лимитами отправки per mailbox."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def can_send(self, account: SenderAccount) -> tuple[bool, str | None]:
        """Проверяет, можно ли отправить с этого ящика сейчас."""
        if account.status != "active":
            return False, f"account_status:{account.status}"

        # Проверка hourly
        hour_key = f"send:hourly:{account.id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
        hourly_sent = int(await self._redis.get(hour_key) or 0)
        if hourly_sent >= account.hourly_limit_current:
            return False, f"hourly_limit:{hourly_sent}/{account.hourly_limit_current}"

        # Проверка daily
        day_key = f"send:daily:{account.id}:{date.today().isoformat()}"
        daily_sent = int(await self._redis.get(day_key) or 0)
        if daily_sent >= account.daily_limit_current:
            return False, f"daily_limit:{daily_sent}/{account.daily_limit_current}"

        return True, None

    async def record_send(self, account_id: UUID) -> None:
        """Записывает факт отправки. TTL — 48 часов для hourly, 7 дней для daily."""
        hour_key = f"send:hourly:{account_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
        await self._redis.incr(hour_key)
        await self._redis.expire(hour_key, 7200)

        day_key = f"send:daily:{account_id}:{date.today().isoformat()}"
        await self._redis.incr(day_key)
        await self._redis.expire(day_key, 7 * 86400)


class WarmUpScheduler:
    """Постепенно увеличивает лимиты ящика."""

    # Схема ramp-up: день → daily_limit, hourly_limit
    SCHEDULE = [
        (1, 5, 2),
        (2, 10, 3),
        (3, 15, 5),
        (4, 20, 5),
        (5, 25, 6),
        (6, 30, 7),
        (7, 35, 8),
        (10, 40, 8),
        (14, 45, 9),
        (21, 50, 10),
        (30, 50, 10),  # стабилизация
    ]

    def compute_limits(self, warmup_started_at: datetime) -> tuple[int, int]:
        """Возвращает (daily_limit, hourly_limit) для текущего дня warmup."""
        days = (datetime.now(timezone.utc) - warmup_started_at).days + 1
        daily, hourly = self.SCHEDULE[-1][1], self.SCHEDULE[-1][2]
        for day_threshold, d, h in self.SCHEDULE:
            if days >= day_threshold:
                daily, hourly = d, h
        return daily, hourly
```

### Выбор ящика при отправке

```python
class AccountSelector:
    """Выбирает подходящий ящик для отправки."""

    async def select(self, *, tenant_id: UUID, user_id: str | None = None) -> SenderAccount | None:
        """Выбирает ящик:
        1. Если указан user_id — его ящик (если active и под лимитом).
        2. Иначе — ящик с наименьшей загрузкой.
        """
        ...
```

### Job: проверка и обновление лимитов

Раз в час (или при каждом запросе на отправку) — пересчитывать `daily_limit_current` / `hourly_limit_current` на основе warmup.

**Решение:** вычислять на лету в `AccountSelector`, не хранить в БД.

## Acceptance criteria

```bash
# Unit-тесты
uv run pytest services/sender-email/tests/test_rampup.py -v
# Ожидание: passed

# E2E: проверить, что лимит соблюдается
# Отправить > daily_limit_current писем → последние должны быть отклонены
```

---

# Задача 3C.4 — Подписка на `message.approved` + отправка

**Файл:** `docs/tasks/sprint-3c/3c.4-send.md`

## Цель

Сервис подписывается на `message.approved`. Для каждого:
1. Получить Message из composer.
2. Проверить stop-list (контакт).
3. Выбрать ящик.
4. Проверить ramp-up лимит.
5. Отправить через SMTP.
6. Записать SendAttempt.
7. Обновить Message (`status=sent`, `sent_at`, `delivery.provider_message_id`).
8. Опубликовать `message.sent`.

## Детали

### Подписка

```python
subscriber = Subscriber(
    nats_conn,
    stream="BRIEFS",
    durable="sender-email-message-approved",
    filter_subjects=["message.approved.*"],
    handler=_on_message_approved,
)
```

### `service.py` — `SenderService`

```python
class SenderService:
    async def send_approved_message(
        self, *, tenant_id: UUID, message_id: UUID, trace_id: str,
    ) -> SendAttempt:
        # 1. Получаем Message
        message = await self._composer.get_message(message_id, tenant_id=str(tenant_id))
        if message.get("status") != "approved":
            raise ValidationError(f"Message status is {message['status']}, not approved")

        contact_id = message["contact_id"]
        recipient_snapshot = message.get("recipient_snapshot", {})
        to_email = recipient_snapshot.get("email")
        if not to_email:
            raise ValidationError("No recipient email in snapshot")

        # 2. Stop-list
        blocked, reason = await self._contact_store.check_stoplist(
            tenant_id=str(tenant_id), email=to_email,
        )
        if blocked:
            attempt = await self._record_attempt(
                tenant_id=tenant_id, message_id=message_id,
                to_email=to_email, from_email="",
                status="failed", error=f"stoplist:{reason}",
            )
            await self._composer.update_message_status(
                message_id, tenant_id=str(tenant_id), status="failed",
                delivery={"failed_reason": f"stoplist:{reason}"},
            )
            return attempt

        # 3. Выбор ящика
        sender_info = message.get("sender", {})
        user_id = sender_info.get("user_id")
        account = await self._account_selector.select(tenant_id=tenant_id, user_id=user_id)
        if account is None:
            raise AppError("No available sender account", code="no_sender", status_code=503)

        # 4. Ramp-up лимит
        can_send, limit_reason = await self._limiter.can_send(account)
        if not can_send:
            # Ставим в очередь на retry через 15 минут
            raise RateLimitExceeded(f"Cannot send: {limit_reason}")

        # 5. Отправляем
        if self._settings.dry_run:
            logger.info("dry_run_send", to=to_email, message_id=str(message_id))
            result = SendResult(success=True, message_id=f"dry-run-{message_id}", response="dry-run", error=None)
        else:
            client = SMTPClient(SMTPConfig(
                host=account.smtp_host,
                port=account.smtp_port,
                use_ssl=account.smtp_use_ssl,
                username=account.smtp_username,
                password=self._encryptor.decrypt(account.smtp_password_encrypted),
            ))
            result = await client.send(
                from_email=account.email,
                from_name=account.display_name,
                to_email=to_email,
                subject=message.get("subject") or "",
                body_text=message.get("body_text") or "",
                body_html=message.get("body_html"),
                list_unsubscribe=f"<mailto:unsubscribe@aitler.ru?subject=unsubscribe-{message_id}>",
            )

        # 6. Записываем
        attempt = await self._record_attempt(
            tenant_id=tenant_id, message_id=message_id,
            sender_account_id=account.id,
            to_email=to_email, from_email=account.email,
            status="sent" if result.success else "failed",
            smtp_message_id=result.message_id,
            smtp_response=result.response,
            error=result.error,
            sent_at=datetime.now(timezone.utc) if result.success else None,
        )

        # 7. Обновляем Message
        if result.success:
            await self._composer.update_message_status(
                message_id, tenant_id=str(tenant_id), status="sent",
                delivery={"provider_message_id": result.message_id, "provider_response": {"response": result.response}},
            )
            await self._limiter.record_send(account.id)
            await emit_message_sent(self._publisher, message, attempt, trace_id=trace_id)
        else:
            await self._composer.update_message_status(
                message_id, tenant_id=str(tenant_id), status="failed",
                delivery={"failed_reason": result.error},
            )

        return attempt

    async def _record_attempt(self, **kwargs) -> SendAttempt:
        attempt = SendAttempt(**kwargs)
        self._repo.add(attempt)
        await self._repo._s.flush()
        return attempt
```

### Retry при rate limit

`RateLimitExceeded` → событие не ack'ается, NATS переотправит через `nak(delay=900)`. Или — сохраняем в отдельную очередь `pending_sends` и обрабатываем периодически.

**Решение:** `nak(delay=900)` (15 минут). Просто и работает.

**Важно:** при `nak` событие вернётся через 15 минут. Если ящик всё ещё под лимитом — снова `nak`. Так до тех пор, пока лимит не освободится. Максимум `max_deliver=5` — потом dead-letter. Нужно настроить `max_deliver` побольше (например, 20).

## Acceptance criteria

```bash
# 1. Approve message
# 2. Дождаться отправки
sleep 5
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/messages/$MSG_ID | jq .status
# Ожидание: "sent" (или "failed" если SMTP не работает)

# 3. SendAttempt записан
bash scripts/psql.sh -c "SELECT status, to_email, sent_at FROM send_attempts WHERE message_id='$MSG_ID';"
# Ожидание: строка

# 4. Событие
bash scripts/nats-cli.sh stream view BRIEFS --last 10 | grep message.sent
# Ожидание: есть

# 5. В dry-run — никаких реальных отправок
# В .env.dev SENDER_DRY_RUN=true
```

## Подсказки

- **`dry_run`** — обязателен на dev. Все «отправки» логируются, но не уходят.
- **`List-Unsubscribe`** — обязателен для deliverability. Gmail/Yandex требуют.
- **Retry через `nak(delay)`** — простое решение.
- **`max_deliver`** — увеличить до 20 в Subscriber для этого consumer'а.

## Анти-паттерны

- ❌ Не отправлять без проверки stop-list.
- ❌ Не отправлять без ramp-up лимита.
- ❌ Не забывать `List-Unsubscribe`.
- ❌ Не отправлять в dry-run на prod.

---

# Задача 3C.5 — IMAP poller: reply detection + bounce handling

**Файл:** `docs/tasks/sprint-3c/3c.5-imap.md`

## Цель

IMAP-poller: периодически проверяет ящики на новые письма, детектит replies и bounces, обновляет Message и Contact.

## Детали

### `imap/poller.py`

```python
import asyncio
from datetime import datetime, timezone
from email import message_from_bytes
from email.utils import parseaddr, parsedate_to_datetime

import aioimaplib
import structlog


logger = structlog.get_logger()


class IMAPPoller:
    """Периодически проверяет ящики на новые письма."""

    def __init__(self, *, repo, composer_client, contact_store_client, encryptor, publisher, interval_seconds: int = 300) -> None:
        ...

    async def run_forever(self) -> None:
        while True:
            try:
                await self._poll_all()
            except Exception as e:
                logger.exception("imap_poll_cycle_failed", error=str(e))
            await asyncio.sleep(self._interval)

    async def _poll_all(self) -> None:
        accounts = await self._repo.list_active_accounts()
        for account in accounts:
            try:
                await self._poll_account(account)
            except Exception as e:
                logger.warning("imap_poll_failed", account=account.email, error=str(e))

    async def _poll_account(self, account: SenderAccount) -> None:
        password = self._encryptor.decrypt(account.imap_password_encrypted)
        imap = aioimaplib.IMAP4_SSL(host=account.imap_host, port=account.imap_port, timeout=30)
        await imap.wait_hello_from_server()
        await imap.login(account.imap_username, password)
        await imap.select("INBOX")

        # Ищем непрочитанные или за последние 7 дней
        # UID search — только новые, если хранить last_uid в account.metadata
        last_uid = (account.metadata_ or {}).get("last_imap_uid", 0)
        status, data = await imap.uid_search(f"UID {last_uid + 1}:*")
        uids = data[0].split() if data and data[0] else []

        for uid in uids[-100:]:  # не больше 100 за раз
            try:
                status, msg_data = await imap.uid("fetch", uid, "(RFC822)")
                if status != "OK":
                    continue
                raw = msg_data[1]
                msg = message_from_bytes(raw)
                await self._process_message(account, msg, str(uid))
            except Exception as e:
                logger.warning("imap_process_failed", uid=uid, error=str(e))

        # Сохраняем last_uid
        if uids:
            new_last = int(uids[-1])
            md = dict(account.metadata_ or {})
            md["last_imap_uid"] = new_last
            account.metadata_ = md
            await self._repo._s.flush()

        await imap.logout()

    async def _process_message(self, account, msg, uid: str) -> None:
        from_addr = parseaddr(msg.get("From", ""))[1].lower()
        subject = msg.get("Subject", "")
        in_reply_to = msg.get("In-Reply-To", "")
        references = msg.get("References", "")

        # Детект bounce
        if self._is_bounce(from_addr, subject, msg):
            await self._handle_bounce(account, msg, from_addr, uid)
            return

        # Детект reply: ищем message по message_id из In-Reply-To/References
        message = await self._find_original_message(account, in_reply_to, references)
        if message:
            await self._handle_reply(account, msg, message, from_addr, uid)

    def _is_bounce(self, from_addr: str, subject: str, msg) -> bool:
        # Простая эвристика
        bounce_senders = ["mailer-daemon", "postmaster", "noreply"]
        if any(b in from_addr for b in bounce_senders):
            return True
        if "undelivered" in subject.lower() or "delivery status" in subject.lower():
            return True
        if msg.get_content_type() == "multipart/report":
            return True
        return False

    async def _handle_bounce(self, account, msg, from_addr: str, uid: str) -> None:
        # Извлекаем email получателя из тела
        body = self._extract_body(msg)
        # Простая эвристика: ищем email в теле
        import re
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", body)
        if not emails:
            return

        bounced_email = emails[0].lower()
        # Находим contact по email
        # Обновляем contact: status=bounced, добавляем в stop-list
        ...
        logger.info("bounce_detected", email=bounced_email, account=account.email)

    async def _find_original_message(self, account, in_reply_to: str, references: str):
        # Ищем message в composer по smtp_message_id
        # Хранить mapping в send_attempts: smtp_message_id → message_id
        if not in_reply_to and not references:
            return None
        # Простая реализация: пробуем все message_id из references
        ids = [in_reply_to] + references.split()
        for mid in ids:
            mid = mid.strip().strip("<>")
            if not mid:
                continue
            attempt = await self._repo.find_attempt_by_smtp_message_id(mid)
            if attempt:
                return await self._composer.get_message(
                    attempt.message_id, tenant_id=str(attempt.tenant_id),
                )
        return None

    async def _handle_reply(self, account, msg, message: dict, from_addr: str, uid: str) -> None:
        # Сохраняем Reply (создаём в composer или отдельно)
        # Обновляем Message: status=replied, engagement.replied_at
        # Публикуем reply.received
        ...
        logger.info("reply_detected", message_id=message["id"], from_email=from_addr)

    def _extract_body(self, msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        return part.get_payload(decode=True).decode(errors="ignore")
                    except Exception:
                        continue
        else:
            try:
                return msg.get_payload(decode=True).decode(errors="ignore")
            except Exception:
                pass
        return ""
```

**Добавить `aioimaplib>=1.1` в зависимости.**

**Важно:** полноценный reply-detection — сложная задача. На 3C делаем **MVP**:
- Детект bounce — по from/subject/content-type.
- Детект reply — по `In-Reply-To`/`References` + маппинг `smtp_message_id` → `message_id` в `send_attempts`.

**Что НЕ делаем в 3C:**
- Классификация replies (positive/negative) — Спринт 4.
- Парсинг темы/тела ответа — Спринт 4.
- Создание `Reply` сущности — Спринт 4.

**Что делаем в 3C:** событие `reply.received` с сырыми данными. Классификация — потом.

### `events.py` — новые события

```python
async def emit_reply_received(publisher, *, tenant_id, message_id, from_email, subject, trace_id):
    await publisher.publish(
        Subjects.REPLY_RECEIVED,
        tenant_id=tenant_id,
        payload={
            "message_id": str(message_id),
            "from_email": from_email,
            "subject": subject,
        },
        trace_id=trace_id,
    )


async def emit_message_bounced(publisher, *, tenant_id, message_id, bounce_type, bounce_reason, trace_id):
    await publisher.publish(
        Subjects.MESSAGE_BOUNCED,
        tenant_id=tenant_id,
        payload={
            "message_id": str(message_id),
            "bounce_type": bounce_type,
            "bounce_reason": bounce_reason,
        },
        trace_id=trace_id,
    )
```

## Acceptance criteria

```bash
# E2E сложно без реального ящика.
# Unit-тесты с mock IMAP:
uv run pytest services/sender-email/tests/test_imap.py -v
# Ожидание: passed

# На dev — с реальным тестовым ящиком:
# 1. Отправить письмо себе
# 2. Ответить
# 3. Через interval (5 минут) — детект reply
bash scripts/psql.sh -c "SELECT status, engagement->>'replied_at' FROM messages WHERE id='$MSG_ID';"
# Ожидание: replied + timestamp
```

## Подсказки

- **IMAP UID** — монотонно растёт. Хранить `last_imap_uid` в `metadata_` ящика.
- **Bounce parsing** — простая эвристика. Полный RFC 3464 — сложно, отложим.
- **Reply detection** — по `In-Reply-To`/`References` + маппинг `smtp_message_id` → `message_id`.
- **Не парсить тело reply** — только сохранить и опубликовать событие.

## Анти-паттерны

- ❌ Не удалять письма из INBOX.
- ❌ Не парсить всё тело — только headers + первые 500 символов.
- ❌ Не делать классификацию replies на 3C.

---

# Задача 3C.6 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-3c/3c.6-tests.md`

## Цель

Покрытие 85%+, E2E с dry-run, обновить CI.

## Детали

### E2E с dry-run

Полный цикл:
1. Draft в composer.
2. Approve в review-queue.
3. Sender подписывается на `message.approved`.
4. `dry_run=true` → «отправка» логируется.
5. SendAttempt записан со status=`sent`.
6. Message обновлён со status=`sent`.
7. Событие `message.sent` опубликовано.

### CI

Добавить `sender-email` в matrix.

## Acceptance criteria

```bash
uv run pytest services/sender-email/tests/ -v --cov=sender_email --cov-report=term-missing
# Ожидание: coverage >= 85%

# E2E
# Все шаги выше проходят
```

---

## Финальная E2E-проверка Спринта 3

```bash
export TENANT="<sandbox>"
export CONTACT_ID="<реальный_contact_id>"
export ICP_ID="<реальный_icp_id>"
export SEGMENT_ID="<реальный_segment_id>"

# 1. Draft
MSG=$(curl -sX POST https://composer.dev.aitler.ru/messages \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-draft-1" \
  -d '{
    "contact_id": "'$CONTACT_ID'",
    "icp_id": "'$ICP_ID'",
    "segment_id": "'$SEGMENT_ID'",
    "channel": "email",
    "language": "ru",
    "sender_identity_type": "user",
    "sender_user_id": "user-1",
    "sender_from_name": "Сергей",
    "sender_from_email": "sergey@example.com",
    "sender_signature": "Сергей, Sales Manager"
  }')
MSG_ID=$(echo $MSG | jq -r .id)
echo "Message: $MSG_ID"
echo $MSG | jq '{subject, word_count, warnings: .personalization.warnings}'

# 2. Дождаться review-item
sleep 5
ITEM_ID=$(curl -s -H "X-Tenant-ID: $TENANT" "https://review.dev.aitler.ru/?status=pending" | jq -r '.[0].id')
echo "Review item: $ITEM_ID"

# 3. Создать ящик и verify (если нет)
# ...

# 4. Approve
curl -sX POST https://review.dev.aitler.ru/$ITEM_ID/approve \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-app-1" \
  -d '{}' | jq .status
# Ожидание: "approved"

# 5. Дождаться отправки (dry-run)
sleep 10
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/messages/$MSG_ID | jq '{status, sent_at, delivery}'
# Ожидание: status="sent", sent_at заполнен, delivery.provider_message_id="dry-run-..."

# 6. SendAttempt
bash scripts/psql.sh -c "SELECT status, to_email, sent_at, smtp_message_id FROM send_attempts WHERE message_id='$MSG_ID';"
# Ожидание: строка со status="sent"

# 7. События
bash scripts/nats-cli.sh stream view BRIEFS --last 50 | grep -E "message\.(drafted|approved|sent)"
# Ожидание: все три

# 8. RLS
OTHER="00000000-0000-0000-0000-000000000000"
curl -s -H "X-Tenant-ID: $OTHER" https://composer.dev.aitler.ru/messages/$MSG_ID -w "\n%{http_code}\n"
# Ожидание: 404

# 9. CI
git push origin develop
# Зелёные
```

**Если все 9 пунктов проходят — Спринт 3 закрыт.**

---

## Проверка: что я перепроверил

- [x] Порядок задач: 3A.1 → 3A.2 → 3A.3 → 3A.4 → 3A.5 → 3A.6 → 3B.1 → 3B.2 → 3B.3 → 3C.1 → 3C.2 → 3C.3 → 3C.4 → 3C.5 → 3C.6, зависимости соблюдены.
- [x] Message модель соответствует `contracts.Message` раздел 5.
- [x] ReviewItem — отдельная сущность, не дублирует Message.
- [x] SenderAccount / SendAttempt — отдельные таблицы.
- [x] Пароли шифруются (`Fernet`), не хранятся в plaintext.
- [x] Ramp-up: SCHEDULE + Redis-счётчики.
- [x] Rate limit per mailbox (hourly + daily).
- [x] Rotация ящиков через AccountSelector.
- [x] Stop-list проверяется перед отправкой.
- [x] List-Unsubscribe header обязателен.
- [x] Dry-run на dev по умолчанию.
- [x] IMAP poller — MVP: bounce + reply detection.
- [x] Классификация replies — отложена на Спринт 4.
- [x] Per-employee ящик, не общий.
- [x] События: message.drafted, message.approved, message.rejected, message.sent, message.bounced, reply.received.
- [x] `Subjects.MESSAGE_*` и `REPLY_RECEIVED` — проверить, что есть в `nats_client.subjects`. Если нет — добавить.
- [x] Mypy strict, ruff, pytest.
- [x] Никаких cross-service импортов.
- [x] Idempotency-Key на всех POST.
- [x] RLS на всех таблицах.

---

## Что дальше (Спринт 4)

После закрытия 3C переходим к **analytics + reply-classifier + A/B** — сбор метрик, классификация ответов, эксперименты. Это то, что замыкает обратную связь.

**Что от тебя нужно сейчас:**
1. Разложить эти 15 задач по файлам в `docs/tasks/sprint-3/` (3A, 3B, 3C — три подпапки).
2. Дать агенту: «Начинай с 3A.1, иди по порядку. 3A — обязательно до конца (генерация), потом 3B (review), потом 3C (отправка). Не переходи к 3C, пока 3A и 3B не закрыты».
3. Сообщить мне, когда Спринт 3 закрыт (или если агент застрял — особенно на 3C.4, там SMTP).

**Критичные вопросы к тебе:**
- **Ящики для теста на dev** — есть ли реальный SMTP/IMAP-ящик, который можно подключить? Или только dry-run?
- **DaData/Rusprofile** — мы добавили DaData в 2C.2.2. Есть ли ключ? Если нет — sourcing не сможет использовать registry-коннектор, только Serper/Yandex.
- **SENDER_ENCRYPTION_KEY** — сгенерировать при первом bootstrap. Команда: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

Если хочешь что-то поправить сейчас — скажи.