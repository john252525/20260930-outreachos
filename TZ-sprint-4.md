# Спринт 4 — analytics + reply-classifier + A/B experiments

Проверил: зависимости от Спринта 0, 1, 2A, 2B, 2C, 3 соблюдены, порядок задач логичен, acceptance criteria проверяемы, нет противоречий с `docs/contracts.md`. Учёл, что Спринт 4 — **замыкает обратную связь**. Без него система работает «вслепую»: письма уходят, ответы приходят, но мы не знаем, что работает, а что нет.

## Что даёт Спринт 4

1. **Reply classification.** Каждый ответ классифицируется: positive / negative / not_interested / wrong_person / auto_reply / question / unsubscribe / out_of_office. Это позволяет считать не просто «reply rate», а «positive reply rate» — главную метрику outreach.
2. **A/B experiments.** Первый класс-гражданин системы. Позволяет проверять гипотезы: тема письма, оффер, CTA, тон, время отправки. Система сама решает, когда эксперимент завершён (статистическая значимость), и публикует `experiment.variant_won`.
3. **Analytics.** Считает метрики по осям: tenant × segment × template × channel × mailbox × time. Reply rate, positive reply rate, meetings booked, bounce rate, spam rate. Это то, на что смотрит человек, чтобы понять «работает или нет».

## Разбивка на под-спринты

**4A — reply-classifier.** Изолированный LLM-сервис. Вход: сырой reply (from, subject, body). Выход: классификация + suggested next action. Событие `reply.classified`.

**4B — analytics-service.** Считает метрики. Читает из БД всех сервисов (messages, send_attempts, replies). Даёт API для дашбордов. Плюс materialized views для тяжёлых агрегатов.

**4C — experiments.** A/B-движок. Управляет экспериментами, распределяет варианты, считает статистику, объявляет победителя.

**Порядок:** 4A → 4B → 4C. Потому что 4C опирается на метрики из 4B, а 4B опирается на классификацию из 4A.

**Что НЕ в этом спринте:**
- UI дашбордов — Metabase/Grafana подключаются отдельно, не в коде.
- Auto-revision писем на основе метрик (например, «если reply rate < 2%, автоматически переписать оффер») — это Спринт 5.
- Прогнозные модели (какой сегмент даст лучший reply rate) — Спринт 5+.
- Мульти-armed bandit для распределения вариантов — Спринт 5. На 4C — классический A/B с фиксированными весами.

---

# 4A — `reply-classifier`

## Что такое reply-classifier и почему изолирован

Это **чистый LLM-сервис**. Вход: сырой reply (From, Subject, Body, In-Reply-To). Выход: структурированная классификация по контракту `contracts.Reply` раздел 6.

**Ключевые принципы:**
1. **Не отвечает.** Только классифицирует. Ответы — задача composer (follow-up) или человека.
2. **Детерминированный fallback.** Если LLM не смог — правила (regex на out-of-office, unsubscribe и т.д.).
3. **Конфиденциальность.** Тело письма обрабатывается, но не логируется полностью. В БД хранится, но с ограничением доступа.
4. **Мультиязычность.** RU + EN. Промпт с указанием языка.
5. **Уверенность.** Каждая классификация имеет `confidence`. Если < 0.6 — помечаем для ручного ревью.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         reply-classifier             │
                    │                                       │
   NATS subscribe ─►│  reply.received (из sender-email)     │
                    │       │                               │
                    │       ▼                               │
                    │  ReplyService                         │
                    │       │                               │
                    │       ├──► LLMClassifier ─────────────┼──► llm-gateway
                    │       ├──► RuleBasedFallback          │
                    │       ├──► ReplyRepository            │
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - reply.classified                  │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                                   Postgres
                                  (replies)
```

**Модель данных:** таблица `replies`, соответствует `contracts.Reply`.

---

# Задача 4A.1 — Каркас `reply-classifier` + модель Reply

**Файл:** `docs/tasks/sprint-4a/4a.1-bootstrap.md`

## Цель

Создать каркас сервиса, определить SQLAlchemy-модель `Reply` со всеми полями из `docs/contracts.md` раздел 6, сделать миграцию с RLS. Подписаться на `reply.received` из sender-email.

## Зависимости

Спринт 3 закрыт.

## Что создать

```
services/reply-classifier/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_replies.py
├── src/reply_classifier/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── events.py
│   ├── classifier/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── llm_classifier.py
│   │   ├── rule_fallback.py
│   │   └── composite.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py             # копия
│   │   ├── json_utils.py         # копия
│   │   ├── schemas.py
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── classify_reply.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── composer_client.py
│   │   └── contact_store_client.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_llm_classifier.py
    ├── test_rule_fallback.py
    ├── test_composite.py
    └── test_e2e.py
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "reply-classifier"
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
    "llm-client",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/reply_classifier"]
```

### `config.py`

```python
from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field("reply-classifier", alias="SERVICE_NAME")
    llm_gateway_url: str = Field(..., alias="LLM_GATEWAY_URL")
    composer_service_url: str = Field(..., alias="COMPOSER_SERVICE_URL")
    contact_store_url: str = Field(..., alias="CONTACT_STORE_URL")

    # LLM
    llm_model: str = Field("deepseek-chat", alias="REPLY_LLM_MODEL")
    llm_temperature: float = Field(0.1, alias="REPLY_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(1024, alias="REPLY_LLM_MAX_TOKENS")

    # Classification
    min_confidence: float = Field(0.6, alias="REPLY_MIN_CONFIDENCE")
    max_body_length: int = Field(10_000, alias="REPLY_MAX_BODY_LENGTH")

    # NATS
    nats_durable_name: str = Field("reply-classifier", alias="NATS_DURABLE_NAME")
```

### `models.py`

Одна таблица `replies`, соответствует `contracts.Reply` раздел 6.

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import (
    MetadataMixin,
    SchemaVersionMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Reply(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "replies"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    contact_id: Mapped[UUID] = mapped_column(nullable=False, index=True)

    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Сырой контент
    from_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Headers (для threading)
    in_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    references: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id_header: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Классификация
    classification: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {category, confidence, sentiment, intent, extracted_questions, extracted_actions, classified_by, classified_at}

    # Suggested next action
    suggested_next_action: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {action, reason, draft_reply}

    # Обработка человеком
    handled_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Статус
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending | classified | needs_review | handled | archived

    __table_args__ = (
        Index("ix_replies_tenant_message", "tenant_id", "message_id"),
        Index("ix_replies_tenant_contact", "tenant_id", "contact_id"),
        Index("ix_replies_tenant_status", "tenant_id", "status"),
        Index("ix_replies_tenant_received", "tenant_id", "received_at"),
        Index("ix_replies_tenant_category", "tenant_id", "classification"),
    )
```

**Важно:** `classification.category` — часто запрашиваемое поле. Для индексации по JSONB используем GIN. Простой GIN по всему `classification` — универсально. Более точечный — вынести `category` в отдельную колонку. **Решение:** вынести `category` в отдельную колонку для быстрых запросов:

```python
category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
```

Это дублирует данные из `classification`, но даёт быстрые индексы. Синхронизация — в `service.py`.

### Миграция

```python
def upgrade() -> None:
    op.create_table(
        "replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_email", sa.String(320), nullable=False),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("raw_content", sa.Text, nullable=False),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("in_reply_to", sa.String(255), nullable=True),
        sa.Column("references", sa.Text, nullable=True),
        sa.Column("message_id_header", sa.String(255), nullable=True),
        sa.Column("classification", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("classification_confidence", sa.Float, nullable=True),
        sa.Column("suggested_next_action", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("handled_by", sa.String(128), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_replies_tenant_message", "replies", ["tenant_id", "message_id"])
    op.create_index("ix_replies_tenant_contact", "replies", ["tenant_id", "contact_id"])
    op.create_index("ix_replies_tenant_status", "replies", ["tenant_id", "status"])
    op.create_index("ix_replies_tenant_received", "replies", ["tenant_id", "received_at"])
    op.create_index("ix_replies_tenant_category", "replies", ["tenant_id", "category"])
    op.create_index("ix_replies_tenant_category_conf", "replies", ["tenant_id", "category", "classification_confidence"])

    op.execute("ALTER TABLE replies ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY replies_tenant_isolation ON replies
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS replies_tenant_isolation ON replies")
    op.drop_table("replies")
```

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  reply-classifier:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/reply-classifier/Dockerfile
    container_name: outreach-reply-classifier
    environment:
      <<: *common-env
      SERVICE_NAME: reply-classifier
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/9
      LLM_GATEWAY_URL: http://llm-gateway:8000
      COMPOSER_SERVICE_URL: http://composer-service:8000
      CONTACT_STORE_URL: http://contact-store:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
      llm-gateway:
        condition: service_started
      composer-service:
        condition: service_started
      contact-store:
        condition: service_started
    labels:
      caddy: reply-classifier.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

Обновить `scripts/migrate.sh` — добавить `reply-classifier`.

### Dockerfile

Скопировать из `brief-service/Dockerfile`, поменять `--package reply-classifier` и `CMD`.

## Acceptance criteria

```bash
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm reply-classifier alembic upgrade head
# Ожидание: Applying 0001_create_replies... OK

docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d reply-classifier
# Ожидание: service_started

curl -fsS https://reply-classifier.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

bash scripts/psql.sh -c "\d+ replies"
# Ожидание: таблица есть, RLS enabled

curl -fsS https://reply-classifier.dev.aitler.ru/openapi.json | jq .info.title
# Ожидание: "Reply Classifier"
```

## Подсказки

- **`category` и `classification_confidence` вынесены** в отдельные колонки для быстрых запросов. Синхронизация — в сервисе после классификации.
- **`raw_content`** — полное тело письма. Может быть большим. Ограничение `max_body_length` применяется до сохранения.
- **`status="pending"`** — изначально. После классификации → `classified` или `needs_review`.
- **`metadata_`** — для расширений (например, `thread_id`, `gmail_labels`).

## Анти-паттерны

- ❌ Не хранить полный HTML — только текст.
- ❌ Не забывать RLS.
- ❌ Не делать `category` только в JSONB — нужен индекс.

---

# Задача 4A.2 — Rule-based fallback classifier

**Файл:** `docs/tasks/sprint-4a/4a.2-rule-fallback.md`

## Цель

Реализовать детерминированный классификатор на правилах. Обрабатывает очевидные случаи без LLM: auto-reply, out-of-office, unsubscribe, bounce. Экономит токены и работает быстро.

## Зависимости

4A.1.

## Что создать

```
services/reply-classifier/src/reply_classifier/classifier/
├── base.py
└── rule_fallback.py

services/reply-classifier/tests/
└── test_rule_fallback.py
```

## Детали

### `base.py`

```python
from dataclasses import dataclass, field
from enum import Enum


class ReplyCategory(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NOT_INTERESTED = "not_interested"
    WRONG_PERSON = "wrong_person"
    AUTO_REPLY = "auto_reply"
    QUESTION = "question"
    UNSUBSCRIBE = "unsubscribe"
    OUT_OF_OFFICE = "out_of_office"
    UNKNOWN = "unknown"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class NextAction(str, Enum):
    REPLY = "reply"
    SCHEDULE_MEETING = "schedule_meeting"
    FORWARD_TO_HUMAN = "forward_to_human"
    ADD_TO_NURTURE = "add_to_nurture"
    UNSUBSCRIBE = "unsubscribe"
    CLOSE = "close"


@dataclass
class ClassificationResult:
    category: ReplyCategory
    confidence: float
    sentiment: Sentiment = Sentiment.NEUTRAL
    intent: str | None = None
    extracted_questions: list[str] = field(default_factory=list)
    extracted_actions: list[str] = field(default_factory=list)
    suggested_action: NextAction = NextAction.FORWARD_TO_HUMAN
    suggested_action_reason: str = ""
    classified_by: str = "rule"
    language: str | None = None
```

### `rule_fallback.py`

```python
import re

from reply_classifier.classifier.base import (
    ClassificationResult,
    NextAction,
    ReplyCategory,
    Sentiment,
)


class RuleBasedClassifier:
    """Детерминированный классификатор. Обрабатывает очевидные случаи без LLM."""

    # Out-of-office маркеры
    OOO_PATTERNS = [
        r"out\s+of\s+office",
        r"автоответ",
        r"автоматический ответ",
        r"в\s+отпуске",
        r"не\s+в\s+офисе",
        r"до\s+\d{1,2}[\.\-/]\d{1,2}",
        r"вернусь\s+\d{1,2}",
        r"буду\s+в\s+отпуске",
        r"в\s+командировке",
    ]

    # Auto-reply маркеры
    AUTO_REPLY_PATTERNS = [
        r"это\s+автоматическое\s+сообщение",
        r"this\s+is\s+an\s+automated\s+message",
        r"не\s+отвечайте\s+на\s+это\s+письмо",
        r"do\s+not\s+reply",
        r"письмо\s+получено",
    ]

    # Unsubscribe маркеры
    UNSUB_PATTERNS = [
        r"отпишите?\s+меня",
        r"удалите\s+меня\s+из\s+рассылки",
        r"unsubscribe",
        r"снимите\s+с\s+рассылки",
        r"не\s+пишите\s+мне\s+больше",
        r"stop\s+emailing",
        r"remove\s+me",
    ]

    # Wrong person маркеры
    WRONG_PERSON_PATTERNS = [
        r"я\s+не\s+отвечаю\s+за",
        r"это\s+не\s+моя\s+зона",
        r"обратитесь\s+к",
        r"not\s+my\s+area",
        r"wrong\s+person",
        r"я\s+не\s+в\s+курсе",
        r"этим\s+занимается",
    ]

    # Negative маркеры
    NEGATIVE_PATTERNS = [
        r"не\s+интересно",
        r"не\s+нужно",
        r"спасибо,?\s+не\s+надо",
        r"not\s+interested",
        r"no\s+thanks",
        r"откажитесь\s+от\s+идеи",
        r"мы\s+не\s+заинтересованы",
    ]

    # Positive маркеры (мягкие, LLM уточнит)
    POSITIVE_PATTERNS = [
        r"интересно",
        r"расскажите\s+подробнее",
        r"давайте\s+обсудим",
        r"готовы\s+обсудить",
        r"пришлите\s+предложение",
        r"хочу\s+узнать",
        r"let'?s\s+talk",
        r"tell\s+me\s+more",
        r"interested",
        r"send\s+more\s+info",
    ]

    def classify(
        self,
        *,
        subject: str | None,
        body: str,
        from_email: str,
    ) -> ClassificationResult | None:
        """Возвращает результат, если уверен, иначе None (передать LLM)."""
        text = f"{subject or ''}\n{body}".lower()

        # 1. Auto-reply — самый надёжный
        if self._matches_any(text, self.AUTO_REPLY_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.AUTO_REPLY,
                confidence=0.95,
                sentiment=Sentiment.NEUTRAL,
                intent="automated response",
                suggested_action=NextAction.CLOSE,
                suggested_action_reason="Автоматический ответ — не требует реакции",
            )

        # 2. Out-of-office
        if self._matches_any(text, self.OOO_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.OUT_OF_OFFICE,
                confidence=0.9,
                sentiment=Sentiment.NEUTRAL,
                intent="out of office",
                suggested_action=NextAction.CLOSE,
                suggested_action_reason="Человек в отпуске/командировке — не требует реакции",
            )

        # 3. Unsubscribe — критично, обрабатываем мгновенно
        if self._matches_any(text, self.UNSUB_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.UNSUBSCRIBE,
                confidence=0.95,
                sentiment=Sentiment.NEGATIVE,
                intent="unsubscribe request",
                suggested_action=NextAction.UNSUBSCRIBE,
                suggested_action_reason="Запрос на отписку — обязательно добавить в stop-list",
            )

        # 4. Wrong person
        if self._matches_any(text, self.WRONG_PERSON_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.WRONG_PERSON,
                confidence=0.85,
                sentiment=Sentiment.NEUTRAL,
                intent="wrong person",
                suggested_action=NextAction.FORWARD_TO_HUMAN,
                suggested_action_reason="Не тот адресат — возможно, стоит найти правильного контакта",
            )

        # 5. Negative
        if self._matches_any(text, self.NEGATIVE_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.NOT_INTERESTED,
                confidence=0.85,
                sentiment=Sentiment.NEGATIVE,
                intent="not interested",
                suggested_action=NextAction.CLOSE,
                suggested_action_reason="Явный отказ — закрыть контакт, не тратить время",
            )

        # 6. Positive — мягкая проверка (LLM уточнит, если есть вопросы)
        if self._matches_any(text, self.POSITIVE_PATTERNS):
            # Извлекаем вопросы (простые)
            questions = self._extract_questions(body)
            return ClassificationResult(
                category=ReplyCategory.QUESTION if questions else ReplyCategory.POSITIVE,
                confidence=0.7,
                sentiment=Sentiment.POSITIVE,
                intent="interest expressed",
                extracted_questions=questions,
                suggested_action=NextAction.REPLY,
                suggested_action_reason="Проявлен интерес — нужно ответить",
            )

        # 7. Не уверены — передаём LLM
        return None

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _extract_questions(body: str) -> list[str]:
        """Извлекает предложения с вопросительным знаком."""
        sentences = re.split(r"(?<=[.!?])\s+", body)
        return [s.strip() for s in sentences if s.strip().endswith("?")][:5]
```

### Тесты

`tests/test_rule_fallback.py`:

```python
import pytest
from reply_classifier.classifier.base import ReplyCategory, NextAction
from reply_classifier.classifier.rule_fallback import RuleBasedClassifier


@pytest.fixture
def clf() -> RuleBasedClassifier:
    return RuleBasedClassifier()


def test_auto_reply(clf):
    result = clf.classify(
        subject="Auto: Re: Ваше предложение",
        body="Это автоматическое сообщение. Ваше письмо получено.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.AUTO_REPLY
    assert result.suggested_action == NextAction.CLOSE


def test_out_of_office(clf):
    result = clf.classify(
        subject="Re: Ваше предложение",
        body="Я в отпуске до 15.10.2026. Вернусь — отвечу.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.OUT_OF_OFFICE


def test_unsubscribe(clf):
    result = clf.classify(
        subject="Re: Ваше предложение",
        body="Пожалуйста, удалите меня из рассылки и не пишите больше.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.UNSUBSCRIBE
    assert result.suggested_action == NextAction.UNSUBSCRIBE


def test_wrong_person(clf):
    result = clf.classify(
        subject="Re: Предложение",
        body="Это не моя зона, обратитесь к Ивану.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.WRONG_PERSON


def test_not_interested(clf):
    result = clf.classify(
        subject="Re: Предложение",
        body="Спасибо, не интересно.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.NOT_INTERESTED


def test_positive_with_question(clf):
    result = clf.classify(
        subject="Re: Предложение",
        body="Интересно. Расскажите подробнее. Какая цена?",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.QUESTION
    assert result.sentiment.value == "positive"
    assert len(result.extracted_questions) >= 1


def test_unknown_returns_none(clf):
    result = clf.classify(
        subject="Re: Предложение",
        body="Хм, посмотрю позже.",
        from_email="x@y.com",
    )
    assert result is None  # передать LLM
```

## Acceptance criteria

```bash
uv run pytest services/reply-classifier/tests/test_rule_fallback.py -v --cov=reply_classifier.classifier.rule_fallback --cov-report=term-missing
# Ожидание: coverage >= 95%

uv run mypy services/reply-classifier
uv run ruff check services/reply-classifier
```

## Подсказки

- **Порядок проверок критичен.** Auto-reply → OOO → Unsubscribe → Wrong person → Negative → Positive → None. Если поменять — можно поймать ложные срабатывания.
- **Unsubscribe проверяется до Negative** — отписка важнее.
- **None на выходе** — это сигнал «передать LLM». Не ошибка.
- **Regex на русском и английском** — оба паттерна в списках.

## Анти-паттерны

- ❌ Не пытаться классифицировать всё через правила — только очевидное.
- ❌ Не забывать про регистр (используем lowercase text).
- ❌ Не возвращать результат с confidence < 0.7 — лучше None.

---

# Задача 4A.3 — LLM classifier

**Файл:** `docs/tasks/sprint-4a/4a.3-llm-classifier.md`

## Цель

LLM-классификатор для случаев, которые не покрыл rule-fallback. Использует structured output через `llm-gateway`.

## Зависимости

4A.1, 4A.2.

## Что создать

- `llm/client.py` (копия из других сервисов).
- `llm/json_utils.py` (копия).
- `llm/schemas.py`.
- `llm/prompts/classify_reply.py`.
- `classifier/llm_classifier.py`.
- Тесты.

## Детали

### `llm/schemas.py`

```python
from pydantic import BaseModel, ConfigDict, Field


class _LLMClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = Field(
        ...,
        pattern="^(positive|negative|not_interested|wrong_person|auto_reply|question|unsubscribe|out_of_office|unknown)$",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    sentiment: str = Field(..., pattern="^(positive|neutral|negative)$")
    intent: str | None = None
    extracted_questions: list[str] = Field(default_factory=list)
    extracted_actions: list[str] = Field(default_factory=list)
    suggested_action: str = Field(
        ...,
        pattern="^(reply|schedule_meeting|forward_to_human|add_to_nurture|unsubscribe|close)$",
    )
    suggested_action_reason: str = ""
    language: str | None = None
    reasoning: str = ""
```

### `llm/prompts/classify_reply.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM = """Ты — эксперт по классификации B2B-ответов на холодные письма.

ПРАВИЛА:
1. Отвечай ТОЛЬКО валидным JSON.
2. Категория — одна из: positive, negative, not_interested, wrong_person, auto_reply, question, unsubscribe, out_of_office, unknown.
3. Confidence: 0.9+ если явно; 0.7-0.9 если очевидно из контекста; 0.5-0.7 если вывод; <0.5 если не уверен (тогда category=unknown).
4. Sentiment: positive | neutral | negative.
5. Extracted questions — реальные вопросы из письма, если есть.
6. Extracted actions — что человек просит сделать (например, "прислать прайс", "позвонить в среду").
7. Suggested action:
   - reply — если человек ждёт ответа
   - schedule_meeting — если явно предлагает встречу
   - forward_to_human — если нужно участие человека (например, "передайте директору")
   - add_to_nurture — если "не сейчас, но может позже"
   - unsubscribe — если просит отписать
   - close — если окончательно отказал или автоответ
8. Language — язык письма (ru / en / ...).

КАТЕГОРИИ:
- positive: явный интерес, "расскажите подробнее", "давайте обсудим"
- negative: отказ без агрессии, "спасибо, не надо"
- not_interested: явный отказ, "не интересно", "не нужно"
- wrong_person: "я не отвечаю за это", "обратитесь к X"
- auto_reply: технический автоответ ("письмо получено")
- question: конкретный вопрос от человека
- unsubscribe: просьба удалить из рассылки
- out_of_office: "в отпуске до X", "вернусь Y"
- unknown: не удаётся классифицировать

Будь консервативен: если сомневаешься — category=unknown, confidence < 0.5.
"""


USER_TEMPLATE = """Классифицируй ответ на холодное письмо.

Исходное письмо (что мы отправили):
<original>
От: {original_from}
Тема: {original_subject}
{original_body}
</original>

Ответ:
<reply>
От: {from_email}
Имя: {from_name}
Тема: {subject}
{body}
</reply>

Верни JSON:
{{
  "category": "...",
  "confidence": 0.0,
  "sentiment": "...",
  "intent": "string | null",
  "extracted_questions": ["string"],
  "extracted_actions": ["string"],
  "suggested_action": "...",
  "suggested_action_reason": "string",
  "language": "ru | en | ...",
  "reasoning": "string (1-2 предложения, почему такая классификация)"
}}
"""


def build_classify_prompt(
    *,
    original_from: str,
    original_subject: str,
    original_body: str,
    from_email: str,
    from_name: str | None,
    subject: str | None,
    body: str,
    max_body_length: int = 10_000,
) -> Prompt:
    return Prompt(
        system=SYSTEM,
        user=USER_TEMPLATE.format(
            original_from=original_from,
            original_subject=original_subject or "(нет темы)",
            original_body=original_body[:2000],
            from_email=from_email,
            from_name=from_name or "(неизвестно)",
            subject=subject or "(нет темы)",
            body=body[:max_body_length],
        ),
        task_type="reply_classify_v1",
    )
```

**Важно:** оригинальное письмо передаётся **обрезанным** до 2000 символов — для контекста. Ответ — до `max_body_length`.

### `classifier/llm_classifier.py`

```python
import structlog

from reply_classifier.classifier.base import (
    ClassificationResult,
    NextAction,
    ReplyCategory,
    Sentiment,
)
from reply_classifier.llm.client import LLMClient
from reply_classifier.llm.prompts.classify_reply import build_classify_prompt
from reply_classifier.llm.schemas import _LLMClassification


logger = structlog.get_logger()


class LLMClassifier:
    def __init__(self, llm: LLMClient, *, max_body_length: int = 10_000) -> None:
        self._llm = llm
        self._max_body_length = max_body_length

    async def classify(
        self,
        *,
        tenant_id: str,
        original_message: dict,
        from_email: str,
        from_name: str | None,
        subject: str | None,
        body: str,
        trace_id: str = "",
    ) -> ClassificationResult:
        prompt = build_classify_prompt(
            original_from=(original_message.get("sender") or {}).get("from_email") or "",
            original_subject=original_message.get("subject") or "",
            original_body=original_message.get("body_text") or "",
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body=body,
            max_body_length=self._max_body_length,
        )

        result = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=_LLMClassification,
            trace_id=trace_id,
            temperature=0.1,
            max_tokens=1024,
        )

        logger.info(
            "reply_llm_classified",
            category=result.category,
            confidence=result.confidence,
            language=result.language,
        )

        return ClassificationResult(
            category=ReplyCategory(result.category),
            confidence=result.confidence,
            sentiment=Sentiment(result.sentiment),
            intent=result.intent,
            extracted_questions=result.extracted_questions,
            extracted_actions=result.extracted_actions,
            suggested_action=NextAction(result.suggested_action),
            suggested_action_reason=result.suggested_action_reason,
            classified_by=f"llm:{self._llm.model_name}",
            language=result.language,
        )
```

## Acceptance criteria

```bash
uv run pytest services/reply-classifier/tests/test_llm_classifier.py -v
# Ожидание: passed

# E2E с реальным LLM
docker compose ... exec -T reply-classifier python - <<'PY'
import asyncio
from reply_classifier.config import Settings
from reply_classifier.llm.client import LLMClient
from reply_classifier.classifier.llm_classifier import LLMClassifier

async def main():
    s = Settings()
    llm = LLMClient(s)
    clf = LLMClassifier(llm)
    result = await clf.classify(
        tenant_id="00000000-0000-0000-0000-000000000001",
        original_message={"sender": {"from_email": "sergey@x.com"}, "subject": "Предложение", "body_text": "Мы производим гидроборты..."},
        from_email="ivan@y.com",
        from_name="Иван Петров",
        subject="Re: Предложение",
        body="Здравствуйте! Интересно, но уточните, какая минимальная партия и сроки поставки?",
    )
    print(f"Category: {result.category}, confidence: {result.confidence}")
    print(f"Questions: {result.extracted_questions}")
    print(f"Action: {result.suggested_action}")
    await llm.close()

asyncio.run(main())
PY
# Ожидание: question, confidence >= 0.7, вопросы извлечены
```

## Подсказки

- **Temperature = 0.1** — классификация должна быть детерминированной.
- **Оригинальное письмо в контексте** — критично. Без него LLM не понимает, на что отвечают.
- **`reasoning`** — не сохраняется в Reply, но логируется. Полезно для отладки.
- **Retry через tenacity** — на транспортные ошибки. Не на 4xx.

## Анти-паттерны

- ❌ Не передавать полное тело оригинального письма — только первые 2000 символов.
- ❌ Не использовать temperature > 0.3 — классификация должна быть стабильной.
- ❌ Не падать при `category=unknown` — это валидный результат.

---

# Задача 4A.4 — Composite classifier + ReplyService + API

**Файл:** `docs/tasks/sprint-4a/4a.4-service.md`

## Цель

Связать rule-fallback и LLM. Подписаться на `reply.received`. API для чтения и ручной обработки.

## Зависимости

4A.1–4A.3.

## Что создать

- `classifier/composite.py`.
- `repository.py` — `ReplyRepository`.
- `service.py` — `ReplyService`.
- `clients/composer_client.py`, `clients/contact_store_client.py`.
- `events.py`.
- `schemas.py`.
- `api/routes.py`, `api/deps.py`.
- Обновить `main.py`.
- Тесты + E2E.

## Детали

### `classifier/composite.py`

```python
import structlog

from reply_classifier.classifier.base import (
    ClassificationResult,
    NextAction,
    ReplyCategory,
    Sentiment,
)
from reply_classifier.classifier.llm_classifier import LLMClassifier
from reply_classifier.classifier.rule_fallback import RuleBasedClassifier


logger = structlog.get_logger()


class CompositeClassifier:
    """Сначала правила, потом LLM."""

    def __init__(
        self,
        rule: RuleBasedClassifier,
        llm: LLMClassifier,
        *,
        min_confidence: float = 0.6,
    ) -> None:
        self._rule = rule
        self._llm = llm
        self._min_confidence = min_confidence

    async def classify(
        self,
        *,
        tenant_id: str,
        original_message: dict,
        from_email: str,
        from_name: str | None,
        subject: str | None,
        body: str,
        trace_id: str = "",
    ) -> ClassificationResult:
        # 1. Пробуем правила
        rule_result = self._rule.classify(
            subject=subject,
            body=body,
            from_email=from_email,
        )
        if rule_result is not None and rule_result.confidence >= self._min_confidence:
            logger.debug("reply_classified_by_rule", category=rule_result.category.value)
            return rule_result

        # 2. Иначе — LLM
        try:
            llm_result = await self._llm.classify(
                tenant_id=tenant_id,
                original_message=original_message,
                from_email=from_email,
                from_name=from_name,
                subject=subject,
                body=body,
                trace_id=trace_id,
            )
            return llm_result
        except Exception as e:
            logger.exception("reply_llm_classify_failed", error=str(e))
            # Fallback на правило, даже если low confidence
            if rule_result is not None:
                return rule_result
            return ClassificationResult(
                category=ReplyCategory.UNKNOWN,
                confidence=0.0,
                sentiment=Sentiment.NEUTRAL,
                suggested_action=NextAction.FORWARD_TO_HUMAN,
                suggested_action_reason="Классификация не удалась — требуется ручной разбор",
                classified_by="fallback",
            )
```

### `repository.py`

```python
class ReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, reply_id: UUID) -> Reply | None:
        return await self._s.get(Reply, reply_id)

    async def get_by_message_and_email(self, *, tenant_id: UUID, message_id: UUID, from_email: str) -> Reply | None:
        stmt = select(Reply).where(
            Reply.tenant_id == tenant_id,
            Reply.message_id == message_id,
            Reply.from_email == from_email,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add(self, reply: Reply) -> Reply:
        self._s.add(reply)
        await self._s.flush()
        return reply

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        category: str | None = None,
        message_id: UUID | None = None,
        contact_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Reply]:
        stmt = select(Reply).where(Reply.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Reply.status == status)
        if category:
            stmt = stmt.where(Reply.category == category)
        if message_id:
            stmt = stmt.where(Reply.message_id == message_id)
        if contact_id:
            stmt = stmt.where(Reply.contact_id == contact_id)
        stmt = stmt.order_by(Reply.received_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
```

### `service.py` — `ReplyService`

```python
class ReplyService:
    def __init__(
        self,
        repo: ReplyRepository,
        classifier: CompositeClassifier,
        composer_client,
        contact_store_client,
        publisher,
        settings: Settings,
    ) -> None:
        ...

    async def process_incoming_reply(
        self,
        *,
        tenant_id: UUID,
        message_id: UUID,
        from_email: str,
        from_name: str | None,
        subject: str | None,
        body: str,
        received_at: datetime,
        in_reply_to: str | None = None,
        references: str | None = None,
        message_id_header: str | None = None,
        trace_id: str = "",
    ) -> Reply:
        # 1. Дедуп: если уже есть reply для этого message+from_email — обновляем
        existing = await self._repo.get_by_message_and_email(
            tenant_id=tenant_id, message_id=message_id, from_email=from_email,
        )
        if existing is not None:
            logger.info("reply_duplicate_skipped", reply_id=str(existing.id))
            return existing

        # 2. Получаем оригинальное message из composer
        original = await self._composer_client.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=trace_id,
        )

        # 3. Обрезаем body
        body = body[: self._settings.max_body_length]

        # 4. Классифицируем
        classification = await self._classifier.classify(
            tenant_id=str(tenant_id),
            original_message=original,
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body=body,
            trace_id=trace_id,
        )

        # 5. Определяем status
        status = "classified"
        if classification.confidence < self._settings.min_confidence:
            status = "needs_review"
        if classification.category == ReplyCategory.UNSUBSCRIBE:
            status = "classified"  # обрабатывается автоматически

        # 6. Создаём Reply
        reply = Reply(
            tenant_id=tenant_id,
            message_id=message_id,
            contact_id=UUID(original["contact_id"]),
            channel="email",
            received_at=received_at,
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            raw_content=body,
            language=classification.language,
            in_reply_to=in_reply_to,
            references=references,
            message_id_header=message_id_header,
            classification={
                "category": classification.category.value,
                "confidence": classification.confidence,
                "sentiment": classification.sentiment.value,
                "intent": classification.intent,
                "extracted_questions": classification.extracted_questions,
                "extracted_actions": classification.extracted_actions,
                "classified_by": classification.classified_by,
                "classified_at": datetime.now(timezone.utc).isoformat(),
            },
            category=classification.category.value,
            classification_confidence=classification.confidence,
            suggested_next_action={
                "action": classification.suggested_action.value,
                "reason": classification.suggested_action_reason,
                "draft_reply": None,
            },
            status=status,
        )
        await self._repo.add(reply)

        # 7. Обновляем Message в composer (status=replied)
        try:
            await self._composer_client.update_message_status(
                message_id,
                tenant_id=str(tenant_id),
                status="replied",
                engagement={
                    "replied_at": received_at.isoformat(),
                    "reply_id": str(reply.id),
                },
            )
        except Exception as e:
            logger.warning("composer_update_failed", message_id=str(message_id), error=str(e))

        # 8. Обновляем Contact
        if classification.category == ReplyCategory.UNSUBSCRIBE:
            # Автоматически отписываем
            try:
                await self._contact_store_client.update_contact_status(
                    UUID(original["contact_id"]),
                    tenant_id=str(tenant_id),
                    status="unsubscribed",
                )
            except Exception as e:
                logger.warning("contact_unsubscribe_failed", error=str(e))
        elif classification.sentiment == Sentiment.POSITIVE:
            try:
                await self._contact_store_client.update_contact_outreach_history(
                    UUID(original["contact_id"]),
                    tenant_id=str(tenant_id),
                    replied_positive=True,
                    last_reply_at=received_at,
                )
            except Exception as e:
                logger.warning("contact_update_failed", error=str(e))

        # 9. Публикуем событие
        await emit_reply_classified(self._publisher, reply, trace_id=trace_id)

        logger.info(
            "reply_classified",
            reply_id=str(reply.id),
            message_id=str(message_id),
            category=classification.category.value,
            confidence=classification.confidence,
            action=classification.suggested_action.value,
        )
        return reply

    async def get(self, reply_id: UUID) -> Reply:
        r = await self._repo.get(reply_id)
        if r is None:
            raise NotFoundError(f"Reply {reply_id} not found")
        return r

    async def list(self, *, tenant_id: UUID, **kwargs) -> list[Reply]:
        return await self._repo.list(tenant_id=tenant_id, **kwargs)

    async def mark_handled(
        self,
        *,
        reply_id: UUID,
        handled_by: str,
        outcome: str | None = None,
    ) -> Reply:
        reply = await self.get(reply_id)
        reply.status = "handled"
        reply.handled_by = handled_by
        reply.handled_at = datetime.now(timezone.utc)
        reply.outcome = outcome
        await self._repo._s.flush()
        return reply
```

**Важно:**
- **Автоматическая отписка** при `UNSUBSCRIBE`. Это критично для репутации.
- **Обновление Contact** при `positive`. Это влияет на аналитику.
- **Дедуп** — если тот же reply приходит повторно, не создаём новый.
- **`status="needs_review"`** при низкой confidence.

### Подписка на NATS

В `main.py`:

```python
from nats_client.subscriber import Subscriber

async def _on_reply_received(envelope) -> None:
    payload = envelope.payload
    # payload: {message_id, from_email, subject} — но нужно получить тело
    # sender-email не передаёт тело в событии (оно большое).
    # Значит, sender-email должен ИЛИ передавать body в событии, ИЛИ reply-classifier должен сам забрать из IMAP.
    # Решение: sender-email передаёт body в событии (ограничив 10k).
    ...

# в lifespan:
subscriber = Subscriber(
    nats_conn,
    stream="BRIEFS",
    durable=settings.nats_durable_name,
    filter_subjects=["reply.received.*"],
    handler=_on_reply_received,
)
await subscriber.start()
asyncio.create_task(subscriber.run_forever())
```

**Важно:** в Спринте 3 событие `reply.received` содержит только `{message_id, from_email, subject}`. Нужно **расширить его** — добавить `body`, `received_at`, `from_name`, `in_reply_to`, `references`, `message_id_header`.

**Обновить `sender-email/events.py`:**

```python
async def emit_reply_received(publisher, *, tenant_id, message_id, from_email, from_name, subject, body, received_at, in_reply_to, references, message_id_header, trace_id):
    await publisher.publish(
        Subjects.REPLY_RECEIVED,
        tenant_id=tenant_id,
        payload={
            "message_id": str(message_id),
            "from_email": from_email,
            "from_name": from_name,
            "subject": subject,
            "body": body[:10000],  # ограничиваем
            "received_at": received_at.isoformat(),
            "in_reply_to": in_reply_to,
            "references": references,
            "message_id_header": message_id_header,
        },
        trace_id=trace_id,
    )
```

**Обновить `sender-email/imap/poller.py`** — передавать всё это в событие.

### `events.py`

```python
async def emit_reply_classified(publisher, reply: Reply, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.REPLY_CLASSIFIED,
        tenant_id=reply.tenant_id,
        payload={
            "reply_id": str(reply.id),
            "message_id": str(reply.message_id),
            "contact_id": str(reply.contact_id),
            "category": reply.category,
            "confidence": reply.classification_confidence,
        },
        trace_id=trace_id,
        correlation_id=reply.message_id,
    )
```

### `schemas.py`

```python
class ReplyRead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    tenant_id: UUID
    message_id: UUID
    contact_id: UUID
    channel: str
    received_at: datetime
    from_email: str
    from_name: str | None
    subject: str | None
    raw_content: str
    language: str | None
    classification: dict
    category: str | None
    classification_confidence: float | None
    suggested_next_action: dict
    handled_by: str | None
    handled_at: datetime | None
    outcome: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ReplySummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    message_id: UUID
    contact_id: UUID
    received_at: datetime
    from_email: str
    subject: str | None
    category: str | None
    classification_confidence: float | None
    suggested_action: str | None
    status: str


class MarkHandledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str | None = None
```

### `api/routes.py`

```python
@router.get("/{reply_id}", response_model=ReplyRead)
async def get_reply(reply_id: UUID, svc=Depends(get_service)) -> ReplyRead:
    reply = await svc.get(reply_id)
    return ReplyRead.model_validate(reply, from_attributes=True)


@router.get("", response_model=list[ReplySummary])
async def list_replies(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    message_id: UUID | None = Query(None),
    contact_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc=Depends(get_service),
) -> list[ReplySummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    replies = await svc.list(
        tenant_id=tenant_id, status=status_filter, category=category,
        message_id=message_id, contact_id=contact_id, limit=limit, offset=offset,
    )
    return [
        ReplySummary(
            id=r.id, message_id=r.message_id, contact_id=r.contact_id,
            received_at=r.received_at, from_email=r.from_email, subject=r.subject,
            category=r.category, classification_confidence=r.classification_confidence,
            suggested_action=(r.suggested_next_action or {}).get("action"),
            status=r.status,
        )
        for r in replies
    ]


@router.post("/{reply_id}/handle", response_model=ReplyRead)
async def mark_handled(
    reply_id: UUID,
    data: MarkHandledRequest,
    request: Request,
    svc=Depends(get_service),
) -> ReplyRead:
    reply = await svc.mark_handled(
        reply_id=reply_id,
        handled_by=request.headers.get("X-User-Id", "anonymous"),
        outcome=data.outcome,
    )
    return ReplyRead.model_validate(reply, from_attributes=True)


@router.post("/{reply_id}/reclassify", response_model=ReplyRead)
async def reclassify(reply_id: UUID, svc=Depends(get_service)) -> ReplyRead:
    """Переклассифицировать (например, после обновления промпта)."""
    ...
```

### `clients/contact_store_client.py`

Добавить метод:

```python
async def update_contact_status(self, contact_id: UUID, *, tenant_id: str, status: str) -> None:
    resp = await self._client.post(
        f"/contacts/{contact_id}/status",
        json={"status": status},
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": f"status-{contact_id}-{status}"},
    )
    resp.raise_for_status()


async def update_contact_outreach_history(
    self, contact_id: UUID, *, tenant_id: str, replied_positive: bool, last_reply_at: datetime,
) -> None:
    # Нужен endpoint в contact-store. См. ниже.
    ...
```

**Обновить contact-store:**
- `POST /contacts/{id}/status` — уже есть.
- `PATCH /contacts/{id}/outreach-history` — новый endpoint.

```python
# contact-store/src/contact_store/api/routes_contacts.py
@router.patch("/{contact_id}/outreach-history", response_model=ContactRead)
async def update_outreach_history(
    contact_id: UUID,
    data: OutreachHistoryUpdate,
    svc=Depends(get_contact_service),
) -> ContactRead:
    contact = await svc.update_outreach_history(contact_id, data)
    return ContactRead.model_validate(contact, from_attributes=True)


# schemas
class OutreachHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    replied_positive: bool | None = None
    last_reply_at: datetime | None = None
    last_contacted_at: datetime | None = None
```

```python
# service
async def update_outreach_history(self, contact_id: UUID, data: OutreachHistoryUpdate) -> Contact:
    contact = await self.get(contact_id)
    if data.replied_positive is not None:
        contact.replied_positive = data.replied_positive
    if data.last_reply_at is not None:
        contact.last_reply_at = data.last_reply_at
    if data.last_contacted_at is not None:
        contact.last_contacted_at = data.last_contacted_at
    await self._repo._s.flush()
    return contact
```

**Добавить `COMPOSER_MESSAGE_UPDATED`?** Нет — используем существующий `PATCH /messages/{id}` из composer.

## Acceptance criteria

```bash
# E2E
# 1. Отправить письмо (dry-run)
# 2. Симулировать reply через NATS publish напрямую:
docker run --rm --network outreach-net natsio/nats-box:0.16.0 \
  nats -s "nats://$NATS_USER:$NATS_PASSWORD@nats:4222" pub "reply.received.$TENANT" \
  '{"event_type":"reply.received","schema_version":"1.0","occurred_at":"2026-10-02T10:00:00Z","tenant_id":"'$TENANT'","trace_id":"test","producer":"test/0.1","payload":{"message_id":"'$MSG_ID'","from_email":"ivan@example.com","from_name":"Иван","subject":"Re: Предложение","body":"Интересно, расскажите подробнее. Какая цена?","received_at":"2026-10-02T10:00:00Z","in_reply_to":"<...>","references":"","message_id_header":"<...>"}}'

# 3. Проверить Reply
sleep 5
curl -s -H "X-Tenant-ID: $TENANT" "https://reply-classifier.dev.aitler.ru/?message_id=$MSG_ID" | jq '.[0]'
# Ожидание: category="question", status="classified"

# 4. Message обновлён
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/messages/$MSG_ID | jq '.status, .engagement.replied_at'
# Ожидание: "replied", timestamp

# 5. Событие
bash scripts/nats-cli.sh stream view BRIEFS --last 10 | grep reply.classified
# Ожидание: есть

# 6. Отписка
# Симулировать reply с "отпишите меня"
# Проверить, что Contact обновлён на unsubscribed и попал в stop-list
```

## Подсказки

- **Дедуп по `(message_id, from_email)`** — критично, IMAP может вернуть одно письмо дважды.
- **Автоматическая отписка** при `UNSUBSCRIBE` — обязательно. Иначе репутация сгорит.
- **`PATCH /contacts/{id}/outreach-history`** — новый endpoint в contact-store.
- **Обновление `sender-email/events.py`** — передавать body в событии. Это изменение Спринта 3, но критичное.
- **`max_body_length=10_000`** — ограничиваем тело при приёме.

## Анти-паттерны

- ❌ Не создавать Reply дважды для одного письма.
- ❌ Не забывать автоматическую отписку.
- ❌ Не блокировать обработку reply, если composer/contact-store недоступен — логируем и продолжаем.

---

# Задача 4A.5 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-4a/4a.5-tests.md`

## Цель

Покрытие 85%+, E2E с симуляцией reply через NATS, обновить CI.

## Детали

### `tests/conftest.py`

По образцу. Моки: respx для composer, contact-store, llm-gateway.

### `tests/test_e2e.py`

Полный цикл:
1. Mock composer → возвращает message.
2. Mock contact-store → обновления проходят.
3. Mock llm-gateway → классификация.
4. Отправить `reply.received` через NATS.
5. Проверить, что Reply создан, Message обновлён, Contact обновлён.

### CI

Добавить `reply-classifier` в matrix.

## Acceptance criteria

```bash
uv run pytest services/reply-classifier/tests/ -v --cov=reply_classifier --cov-report=term-missing
# Ожидание: coverage >= 85%

uv run mypy services/reply-classifier
uv run ruff check services/reply-classifier

# E2E на dev — см. выше

# CI
git push origin develop
# Зелёные
```

---

# 4B — `analytics-service`

## Что такое analytics-service

Это сервис, который **считает метрики**. Он не владеет данными — он их читает из БД других сервисов (messages, send_attempts, replies, search_jobs, companies, contacts). Даёт API для дашбордов и алертов.

**Ключевые принципы:**
1. **Read-only.** Не пишет в чужие таблицы.
2. **Materialized views** для тяжёлых агрегатов. Обновляются по расписанию.
3. **Мульти-тенантность.** Все запросы — с `tenant_id`.
4. **Гибкость.** Метрики по осям: tenant × segment × template × channel × mailbox × time.
5. **Алерты.** Если reply rate падает ниже порога — публикуем событие.

**Что НЕ делает:**
- Не хранит сырые данные (только агрегаты в MV).
- Не классифицирует (это reply-classifier).
- Не управляет экспериментами (это experiments).

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         analytics-service             │
                    │                                       │
   HTTP GET ───────►│  API: /analytics/*                    │
   /analytics/*     │       │                               │
                    │       ▼                               │
                    │  AnalyticsService                     │
                    │       │                               │
                    │       ├──► MetricsRepository          │
                    │       │       │                       │
                    │       │       ├──► Postgres (read)    │
                    │       │       │   - messages          │
                    │       │       │   - send_attempts     │
                    │       │       │   - replies           │
                    │       │       │   - companies         │
                    │       │       │   - contacts          │
                    │       │       │   - materialized views│
                    │       │       └───────────────────────┤
                    │       │                               │
                    │       ├──► AlertEngine                 │
                    │       └──► Publisher (NATS)            │
                    │                                       │
                    │  Events:                              │
                    │   - analytics.alert                   │
                    └──────────────────────────────────────┘
```

**Схема БД:** одна схема `analytics` с materialized views.

---

# Задача 4B.1 — Каркас + схема analytics + MV

**Файл:** `docs/tasks/sprint-4b/4b.1-bootstrap.md`

## Цель

Создать каркас сервиса, схему `analytics`, materialized views для основных метрик. Сервис читает чужие таблицы (read-only роль).

## Зависимости

4A закрыт.

## Что создать

```
services/analytics-service/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_analytics_schema.py
├── src/analytics_service/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── message_metrics.py
│   │   ├── reply_metrics.py
│   │   ├── sender_metrics.py
│   │   └── sourcing_metrics.py
│   ├── alerts/
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── events.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
```

## Детали

### `pyproject.toml`

```toml
[project]
name = "analytics-service"
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

[tool.hatch.tool.targets.wheel]
packages = ["src/analytics_service"]
```

### `config.py`

```python
from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field("analytics-service", alias="SERVICE_NAME")

    # MV refresh
    mv_refresh_interval_seconds: int = Field(300, alias="ANALYTICS_MV_REFRESH_INTERVAL")
    mv_refresh_enabled: bool = Field(True, alias="ANALYTICS_MV_REFRESH_ENABLED")

    # Cache
    cache_ttl_seconds: int = Field(60, alias="ANALYTICS_CACHE_TTL")

    # Alerts
    alerts_enabled: bool = Field(True, alias="ANALYTICS_ALERTS_ENABLED")
    alert_reply_rate_threshold: float = Field(0.02, alias="ANALYTICS_ALERT_REPLY_RATE")
    alert_bounce_rate_threshold: float = Field(0.05, alias="ANALYTICS_ALERT_BOUNCE_RATE")
    alert_window_hours: int = Field(24, alias="ANALYTICS_ALERT_WINDOW_HOURS")
```

### Миграция

Создаём **схему** `analytics` (не таблицы), и materialized views.

```python
from alembic import op
import sqlalchemy as sa


revision = "0001_create_analytics_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")

    # Доступ для app-роли
    op.execute("GRANT USAGE ON SCHEMA analytics TO outreach_app")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO outreach_app")
    # На будущее
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO outreach_app")

    # --- MV: daily message metrics по tenant × template × channel ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_message_metrics AS
        SELECT
            m.tenant_id,
            DATE(m.created_at) AS day,
            m.channel,
            m.personalization->>'template_id' AS template_id,
            m.personalization->>'template_version' AS template_version,
            COUNT(*) FILTER (WHERE m.status IN ('sent', 'delivered', 'replied', 'closed')) AS sent_count,
            COUNT(*) FILTER (WHERE m.status = 'bounced') AS bounced_count,
            COUNT(*) FILTER (WHERE m.status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE m.status = 'replied') AS replied_count,
            COUNT(*) FILTER (WHERE m.status = 'approved') AS approved_count,
            COUNT(*) FILTER (WHERE m.status = 'draft') AS draft_count,
            COUNT(*) FILTER (WHERE m.status = 'rejected') AS rejected_count,
            AVG(m.word_count) AS avg_word_count
        FROM messages m
        GROUP BY 1, 2, 3, 4, 5
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_message_metrics_pk
        ON analytics.mv_daily_message_metrics (tenant_id, day, channel, COALESCE(template_id, ''), COALESCE(template_version, ''))
    """)

    # --- MV: daily reply metrics ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_reply_metrics AS
        SELECT
            r.tenant_id,
            DATE(r.received_at) AS day,
            r.category,
            r.channel,
            COUNT(*) AS reply_count,
            AVG(r.classification_confidence) AS avg_confidence,
            COUNT(DISTINCT r.contact_id) AS unique_contacts,
            COUNT(DISTINCT r.message_id) AS unique_messages
        FROM replies r
        WHERE r.status IN ('classified', 'handled')
        GROUP BY 1, 2, 3, 4
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_reply_metrics_pk
        ON analytics.mv_daily_reply_metrics (tenant_id, day, COALESCE(category, ''), channel)
    """)

    # --- MV: sender metrics ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_sender_metrics AS
        SELECT
            sa.tenant_id,
            DATE(sat.sent_at) AS day,
            sa.id AS sender_account_id,
            sa.email AS sender_email,
            COUNT(*) FILTER (WHERE sat.status = 'sent') AS sent_count,
            COUNT(*) FILTER (WHERE sat.status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE sat.status = 'bounced') AS bounced_count
        FROM send_attempts sat
        JOIN sender_accounts sa ON sa.id = sat.sender_account_id
        WHERE sat.sent_at IS NOT NULL
        GROUP BY 1, 2, 3, 4
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_sender_metrics_pk
        ON analytics.mv_daily_sender_metrics (tenant_id, day, sender_account_id)
    """)

    # --- MV: sourcing funnel ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_sourcing_metrics AS
        SELECT
            sj.tenant_id,
            DATE(sj.created_at) AS day,
            sj.icp_id,
            COUNT(*) AS jobs_count,
            SUM(sj.candidates_raw_count) AS raw_count,
            SUM(sj.candidates_normalized_count) AS normalized_count,
            SUM(sj.candidates_persisted_count) AS persisted_count,
            SUM(sj.companies_created) AS companies_created,
            SUM(sj.contacts_created) AS contacts_created,
            SUM(sj.total_cost_usd) AS total_cost_usd,
            AVG(sj.duration_ms) AS avg_duration_ms
        FROM search_jobs sj
        WHERE sj.status = 'completed'
        GROUP BY 1, 2, 3
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_sourcing_metrics_pk
        ON analytics.mv_daily_sourcing_metrics (tenant_id, day, icp_id)
    """)

    # --- MV: funnel overall (по tenant за всё время) ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_funnel AS
        SELECT
            m.tenant_id,
            COUNT(DISTINCT c.id) AS contacts_total,
            COUNT(DISTINCT m.contact_id) AS contacted,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'sent') AS sent,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'replied') AS replied,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'replied' AND EXISTS (
                SELECT 1 FROM replies r WHERE r.message_id = m.id AND r.category IN ('positive', 'question')
            )) AS replied_positive,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'bounced') AS bounced,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'closed') AS closed
        FROM messages m
        LEFT JOIN contacts c ON c.id = m.contact_id AND c.tenant_id = m.tenant_id
        GROUP BY 1
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_mv_funnel_pk ON analytics.mv_funnel (tenant_id)
    """)


def downgrade() -> None:
    for mv in [
        "mv_funnel",
        "mv_daily_sourcing_metrics",
        "mv_daily_sender_metrics",
        "mv_daily_reply_metrics",
        "mv_daily_message_metrics",
    ]:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS analytics.{mv}")
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
```

**Важно:**
- **MV в отдельной схеме** `analytics` — не смешиваются с public.
- **Read-only доступ** для app-роли.
- **Уникальные индексы** на MV — обязательны для `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
- **`COALESCE`** в уникальных индексах — потому что `template_id` может быть NULL.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  analytics-service:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/analytics-service/Dockerfile
    container_name: outreach-analytics-service
    environment:
      <<: *common-env
      SERVICE_NAME: analytics-service
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/10
      ANALYTICS_MV_REFRESH_ENABLED: "true"
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      caddy: analytics.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
```

Обновить `scripts/migrate.sh`.

## Acceptance criteria

```bash
docker compose ... run --rm analytics-service alembic upgrade head
# Ожидание: Applying 0001_create_analytics_schema... OK

docker compose ... up -d analytics-service
curl -fsS https://analytics.dev.aitler.ru/healthz

# MV созданы
bash scripts/psql.sh -c "\dm analytics.*"
# Ожидание: 5 materialized views

# Refresh
bash scripts/psql.sh -c "REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_daily_message_metrics;"
# Ожидание: OK
```

## Подсказки

- **`REFRESH MATERIALIZED VIEW CONCURRENTLY`** — не блокирует чтение. Требует уникальный индекс.
- **MV в схеме `analytics`** — чисто.
- **Read-only доступ** — не давать app-роли INSERT/UPDATE на чужие таблицы.
- **На dev** — можно `REFRESH` без `CONCURRENTLY` (быстрее, но блокирует).

## Анти-паттерны

- ❌ Не делать MV в схеме `public`.
- ❌ Не забывать уникальные индексы — иначе `CONCURRENTLY` не работает.
- ❌ Не давать analytics-service права на запись.

---

# Задача 4B.2 — Metrics repository + service

**Файл:** `docs/tasks/sprint-4b/4b.2-metrics.md`

## Цель

Реализовать чтение метрик из MV и прямых таблиц. API для основных запросов.

## Детали

### `metrics/message_metrics.py`

```python
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MessageMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def daily(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
        channel: str | None = None,
        template_id: str | None = None,
    ) -> list[dict]:
        sql = """
            SELECT day, channel, template_id, template_version,
                   sent_count, bounced_count, failed_count,
                   replied_count, approved_count, draft_count, rejected_count,
                   avg_word_count
            FROM analytics.mv_daily_message_metrics
            WHERE tenant_id = :tid
              AND day BETWEEN :from_date AND :to_date
              AND (:channel IS NULL OR channel = :channel)
              AND (:template_id IS NULL OR template_id = :template_id)
            ORDER BY day DESC, channel
        """
        result = await self._s.execute(text(sql), {
            "tid": str(tenant_id),
            "from_date": from_date,
            "to_date": to_date,
            "channel": channel,
            "template_id": template_id,
        })
        return [dict(r._mapping) for r in result]

    async def by_template(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
    ) -> list[dict]:
        sql = """
            SELECT
                template_id,
                template_version,
                SUM(sent_count) AS sent,
                SUM(replied_count) AS replied,
                SUM(bounced_count) AS bounced,
                SUM(failed_count) AS failed,
                CASE WHEN SUM(sent_count) > 0
                     THEN SUM(replied_count)::float / SUM(sent_count)
                     ELSE 0 END AS reply_rate,
                CASE WHEN SUM(sent_count) > 0
                     THEN SUM(bounced_count)::float / SUM(sent_count)
                     ELSE 0 END AS bounce_rate
            FROM analytics.mv_daily_message_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
            GROUP BY 1, 2
            HAVING SUM(sent_count) > 0
            ORDER BY reply_rate DESC
        """
        result = await self._s.execute(text(sql), {
            "tid": str(tenant_id),
            "from_date": from_date,
            "to_date": to_date,
        })
        return [dict(r._mapping) for r in result]

    async def by_sender(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
    ) -> list[dict]:
        sql = """
            SELECT
                sender_email,
                SUM(sent_count) AS sent,
                SUM(bounced_count) AS bounced,
                SUM(failed_count) AS failed,
                CASE WHEN SUM(sent_count) > 0
                     THEN SUM(bounced_count)::float / SUM(sent_count)
                     ELSE 0 END AS bounce_rate
            FROM analytics.mv_daily_sender_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
            GROUP BY 1
            HAVING SUM(sent_count) > 0
            ORDER BY sent DESC
        """
        result = await self._s.execute(text(sql), {
            "tid": str(tenant_id),
            "from_date": from_date,
            "to_date": to_date,
        })
        return [dict(r._mapping) for r in result]
```

### `metrics/reply_metrics.py`

```python
class ReplyMetrics:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def category_breakdown(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
    ) -> list[dict]:
        sql = """
            SELECT category,
                   SUM(reply_count) AS count,
                   AVG(avg_confidence) AS confidence
            FROM analytics.mv_daily_reply_metrics
            WHERE tenant_id = :tid AND day BETWEEN :from_date AND :to_date
            GROUP BY 1
            ORDER BY count DESC
        """
        ...

    async def positive_reply_rate(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
        segment_id: str | None = None,
        template_id: str | None = None,
    ) -> dict:
        # Считаем через прямые джойны
        sql = """
            WITH sent AS (
                SELECT DISTINCT m.contact_id
                FROM messages m
                WHERE m.tenant_id = :tid
                  AND m.status IN ('sent', 'delivered', 'replied', 'closed')
                  AND m.sent_at BETWEEN :from_ts AND :to_ts
                  AND (:template_id IS NULL OR m.personalization->>'template_id' = :template_id)
            ),
            positive AS (
                SELECT DISTINCT r.contact_id
                FROM replies r
                WHERE r.tenant_id = :tid
                  AND r.category IN ('positive', 'question')
                  AND r.received_at BETWEEN :from_ts AND :to_ts
            )
            SELECT
                (SELECT COUNT(*) FROM sent) AS sent_count,
                (SELECT COUNT(*) FROM positive) AS positive_count,
                CASE WHEN (SELECT COUNT(*) FROM sent) > 0
                     THEN (SELECT COUNT(*) FROM positive)::float / (SELECT COUNT(*) FROM sent)
                     ELSE 0 END AS positive_reply_rate
        """
        ...
```

### `service.py` — `AnalyticsService`

```python
class AnalyticsService:
    def __init__(self, message_metrics, reply_metrics, sender_metrics, sourcing_metrics, cache, settings) -> None:
        ...

    async def get_funnel(self, *, tenant_id: UUID) -> dict:
        """Funnel: contacts → contacted → sent → replied → positive."""
        key = f"analytics:funnel:{tenant_id}"
        cached = await self._cache.get(key)
        if cached:
            return json.loads(cached)

        sql = "SELECT * FROM analytics.mv_funnel WHERE tenant_id = :tid"
        ...
        result = {...}
        await self._cache.setex(key, self._settings.cache_ttl_seconds, json.dumps(result))
        return result

    async def get_overview(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
    ) -> dict:
        """Общий обзор: sent, reply rate, positive reply rate, bounce rate."""
        ...

    async def get_by_template(self, *, tenant_id: UUID, from_date: date, to_date: date) -> list[dict]:
        ...

    async def get_by_sender(self, *, tenant_id: UUID, from_date: date, to_date: date) -> list[dict]:
        ...

    async def get_reply_categories(self, *, tenant_id: UUID, from_date: date, to_date: date) -> list[dict]:
        ...

    async def get_sourcing_stats(self, *, tenant_id: UUID, from_date: date, to_date: date) -> dict:
        ...
```

### API

```python
@router.get("/overview")
async def overview(
    from_date: date = Query(...),
    to_date: date = Query(...),
    svc=Depends(get_service),
) -> dict:
    ...


@router.get("/funnel")
async def funnel(svc=Depends(get_service)) -> dict:
    ...


@router.get("/by-template")
async def by_template(
    from_date: date = Query(...),
    to_date: date = Query(...),
    svc=Depends(get_service),
) -> list[dict]:
    ...


@router.get("/by-sender")
async def by_sender(
    from_date: date = Query(...),
    to_date: date = Query(...),
    svc=Depends(get_service),
) -> list[dict]:
    ...


@router.get("/reply-categories")
async def reply_categories(
    from_date: date = Query(...),
    to_date: date = Query(...),
    svc=Depends(get_service),
) -> list[dict]:
    ...


@router.get("/sourcing")
async def sourcing(
    from_date: date = Query(...),
    to_date: date = Query(...),
    svc=Depends(get_service),
) -> dict:
    ...


@router.get("/segments")
async def segments(
    from_date: date = Query(...),
    to_date: date = Query(...),
    svc=Depends(get_service),
) -> list[dict]:
    """Метрики по сегментам ICP — через JOIN messages с companies и contacts."""
    ...
```

## Acceptance criteria

```bash
# Overview
curl -s -H "X-Tenant-ID: $TENANT" "https://analytics.dev.aitler.ru/overview?from_date=2026-09-01&to_date=2026-10-02" | jq .
# Ожидание: {sent, reply_rate, positive_reply_rate, bounce_rate, ...}

# Funnel
curl -s -H "X-Tenant-ID: $TENANT" https://analytics.dev.aitler.ru/funnel | jq .
# Ожидание: {contacts_total, contacted, sent, replied, replied_positive, bounced, closed}

# By template
curl -s -H "X-Tenant-ID: $TENANT" "https://analytics.dev.aitler.ru/by-template?from_date=2026-09-01&to_date=2026-10-02" | jq .
# Ожидание: список шаблонов с метриками

# Reply categories
curl -s -H "X-Tenant-ID: $TENANT" "https://analytics.dev.aitler.ru/reply-categories?from_date=2026-09-01&to_date=2026-10-02" | jq .
# Ожидание: распределение по категориям
```

## Подсказки

- **Кэш в Redis** на 60 секунд. Метрики не критичны к секундной точности.
- **`REFRESH MATERIALIZED VIEW`** — раз в 5 минут (в фоне). См. задачу 4B.3.
- **`from_date`/`to_date`** — обязательны. Иначе можно случайно запросить всё.

## Анти-паттерны

- ❌ Не считать метрики «на лету» через тяжёлые JOIN'ы без индексов.
- ❌ Не забывать кэш — иначе дашборд будет тормозить.
- ❌ Не возвращать метрики без разбивки по времени.

---

# Задача 4B.3 — MV refresh worker + alerts

**Файл:** `docs/tasks/sprint-4b/4b.3-refresh-alerts.md`

## Цель

Фоновый воркер: раз в N секунд обновляет MV. Плюс alert engine: если метрики ниже порога — публикует `analytics.alert`.

## Детали

### MV refresh worker

```python
import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import text

from analytics_service.config import Settings
from db.session import async_session_factory


logger = structlog.get_logger()


MV_LIST = [
    "analytics.mv_daily_message_metrics",
    "analytics.mv_daily_reply_metrics",
    "analytics.mv_daily_sender_metrics",
    "analytics.mv_daily_sourcing_metrics",
    "analytics.mv_funnel",
]


class MVRefresher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stopped = False

    async def run_forever(self) -> None:
        while not self._stopped:
            try:
                await self._refresh_all()
            except Exception as e:
                logger.exception("mv_refresh_failed", error=str(e))
            await asyncio.sleep(self._settings.mv_refresh_interval_seconds)

    async def _refresh_all(self) -> None:
        async with async_session_factory() as session:
            for mv in MV_LIST:
                try:
                    # Без CONCURRENTLY на dev (быстрее). На prod — CONCURRENTLY.
                    await session.execute(text(f"REFRESH MATERIALIZED VIEW {mv}"))
                    await session.commit()
                    logger.info("mv_refreshed", mv=mv)
                except Exception as e:
                    logger.warning("mv_refresh_error", mv=mv, error=str(e))
                    await session.rollback()

    def stop(self) -> None:
        self._stopped = True
```

**Важно:** на prod — `REFRESH MATERIALIZED VIEW CONCURRENTLY`. Требует уникальный индекс (есть). Медленнее, но не блокирует.

### Alert engine

```python
from datetime import date, timedelta

import structlog

from analytics_service.config import Settings
from analytics_service.events import emit_alert
from analytics_service.repository import MetricsRepository
from nats_client.publisher import Publisher


logger = structlog.get_logger()


class AlertEngine:
    def __init__(self, repo: MetricsRepository, publisher: Publisher, settings: Settings) -> None:
        self._repo = repo
        self._publisher = publisher
        self._settings = settings

    async def check_all(self, *, tenant_id: UUID) -> list[dict]:
        """Проверяет все алерты. Возвращает список сработавших."""
        alerts: list[dict] = []

        # Reply rate
        today = date.today()
        from_date = today - timedelta(days=self._settings.alert_window_hours // 24 or 1)
        overview = await self._repo.get_overview(
            tenant_id=tenant_id, from_date=from_date, to_date=today,
        )
        if overview["sent"] >= 50:  # только при достаточной выборке
            if overview["reply_rate"] < self._settings.alert_reply_rate_threshold:
                alerts.append({
                    "type": "low_reply_rate",
                    "value": overview["reply_rate"],
                    "threshold": self._settings.alert_reply_rate_threshold,
                    "message": f"Reply rate {overview['reply_rate']:.2%} ниже порога {self._settings.alert_reply_rate_threshold:.2%}",
                })

        # Bounce rate
        if overview["sent"] >= 20:
            if overview["bounce_rate"] > self._settings.alert_bounce_rate_threshold:
                alerts.append({
                    "type": "high_bounce_rate",
                    "value": overview["bounce_rate"],
                    "threshold": self._settings.alert_bounce_rate_threshold,
                    "message": f"Bounce rate {overview['bounce_rate']:.2%} выше порога {self._settings.alert_bounce_rate_threshold:.2%}",
                })

        for a in alerts:
            await emit_alert(self._publisher, tenant_id=tenant_id, alert=a, trace_id="")
            logger.warning("analytics_alert", tenant_id=str(tenant_id), **a)

        return alerts

    async def run_forever(self, *, tenant_ids: list[UUID]) -> None:
        import asyncio
        while True:
            for tid in tenant_ids:
                try:
                    await self.check_all(tenant_id=tid)
                except Exception as e:
                    logger.exception("alert_check_failed", tenant_id=str(tid), error=str(e))
            await asyncio.sleep(3600)  # раз в час
```

### `events.py`

```python
async def emit_alert(publisher, *, tenant_id, alert: dict, trace_id: str) -> None:
    await publisher.publish(
        Subjects.ANALYTICS_ALERT,
        tenant_id=tenant_id,
        payload={"alert": alert},
        trace_id=trace_id,
    )
```

**Добавить `ANALYTICS_ALERT` в `nats_client.subjects`.**

### `main.py`

Запустить в фоне:

```python
mv_refresher = MVRefresher(settings)
asyncio.create_task(mv_refresher.run_forever())

# Alert engine — получает список активных tenant'ов
# Простой подход: раз в час читать из tenants
```

## Acceptance criteria

```bash
# MV refresh — в логах
docker compose ... logs --tail=50 analytics-service | grep mv_refreshed
# Ожидание: все 5 MV

# Alert — если метрики низкие
bash scripts/nats-cli.sh stream view LLM_CALLS --last 10 | grep analytics.alert
# Ожидание: если сработал
```

## Подсказки

- **`CONCURRENTLY`** — на prod. На dev можно без.
- **Alert — только при достаточной выборке** (>=50 писем). Иначе шум.
- **Раз в час** — достаточно. Не нужно чаще.

## Анти-паттерны

- ❌ Не рефрешить MV слишком часто — нагрузка на БД.
- ❌ Не алертить при малых выборках.
- ❌ Не забывать про ошибки refresh — логируем и продолжаем.

---

# Задача 4B.4 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-4b/4b.4-tests.md`

## Детали

### E2E

1. Заполнить БД тестовыми данными (messages, send_attempts, replies, search_jobs).
2. Refresh MV.
3. `GET /overview` → корректные цифры.
4. `GET /funnel` → корректный funnel.
5. `GET /by-template` → разбивка по шаблонам.

### CI

Добавить `analytics-service` в matrix.

## Acceptance criteria

```bash
uv run pytest services/analytics-service/tests/ -v --cov=analytics_service --cov-report=term-missing
# Ожидание: coverage >= 80%
```

---

# 4C — `experiments`

## Что такое experiments

Это **A/B-движок**. Он управляет экспериментами: создаёт, распределяет варианты, считает статистику, объявляет победителя.

**Ключевые принципы:**
1. **Эксперимент — first-class citizen.** Создаётся до начала генерации. Применяется в `composer-service`.
2. **Детерминированное распределение.** По хешу `(experiment_id, contact_id)` — чтобы один контакт всегда попадал в один вариант.
3. **Статистическая значимость.** Не «победил по цифрам», а «победил с p < 0.05».
4. **Минимальный sample size.** Не объявляем победителя, пока не набралось N наблюдений на вариант.
5. **Мульти-вариантность.** Не только A/B, но и A/B/C/D.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         experiments-service           │
                    │                                       │
   HTTP POST ──────►│  /experiments                          │
                    │       │                               │
                    │       ▼                               │
                    │  ExperimentService                    │
                    │       │                               │
                    │       ├──► ExperimentRepository       │
                    │       ├──► VariantAssigner (pure)     │
                    │       ├──► StatsEngine (pure)         │
                    │       ├──► AnalyticsClient ───────────┼──► analytics-service
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - experiment.created                │
                    │   - experiment.variant_won            │
                    └──────────────────────────────────────┘
```

---

# Задача 4C.1 — Каркас + модель Experiment

**Файл:** `docs/tasks/sprint-4c/4c.1-bootstrap.md`

## Цель

Создать каркас, определить модель `Experiment`, миграция с RLS.

## Детали

### `models.py`

```python
class Experiment(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )  # draft | running | paused | completed | aborted

    # Scope
    segment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="email")
    icp_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Variable
    variable_type: Mapped[str] = mapped_column(String(32), nullable=False)
    variable_description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Variants (JSONB)
    variants: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # [{id, name, description, template_id, weight}]

    # Metrics
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {primary, secondary}

    # Sample size
    sample_size_target: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    sample_size_per_variant: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    minimum_detectable_effect: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    # Results
    results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {variants: [{variant_id, sent, replied, positive_replied, meetings_booked, primary_metric_value, confidence_interval}], winner_variant_id, is_significant, concluded_at}

    decision: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_experiments_tenant_name"),
        Index("ix_experiments_tenant_status", "tenant_id", "status"),
    )
```

### Миграция

По образцу. RLS.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  experiments-service:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/experiments-service/Dockerfile
    container_name: outreach-experiments-service
    environment:
      <<: *common-env
      SERVICE_NAME: experiments-service
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/11
      ANALYTICS_SERVICE_URL: http://analytics-service:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      analytics-service:
        condition: service_started
    labels:
      caddy: experiments.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
```

Обновить `scripts/migrate.sh`.

## Acceptance criteria

```bash
docker compose ... run --rm experiments-service alembic upgrade head
docker compose ... up -d experiments-service
curl -fsS https://experiments.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\d+ experiments"
```

---

# Задача 4C.2 — Variant assigner + Stats engine

**Файл:** `docs/tasks/sprint-4c/4c.2-assigner-stats.md`

## Цель

Детерминированное распределение контактов по вариантам + статистический движок для определения победителя.

## Детали

### `variant_assigner.py`

```python
import hashlib


class VariantAssigner:
    """Детерминированно распределяет контакты по вариантам.

    Один и тот же (experiment_id, contact_id) всегда даёт один и тот же вариант.
    """

    def assign(
        self,
        *,
        experiment_id: str,
        contact_id: str,
        variants: list[dict],
    ) -> str | None:
        """Возвращает variant_id или None, если вариантов нет."""
        if not variants:
            return None

        # Хеш
        key = f"{experiment_id}:{contact_id}"
        h = hashlib.sha256(key.encode()).hexdigest()
        # Превращаем в число [0, 1)
        bucket = int(h[:8], 16) / 0xFFFFFFFF

        # Кумулятивные веса
        cum = 0.0
        for v in variants:
            cum += v.get("weight", 0.0)
            if bucket < cum:
                return v["id"]

        # Fallback — последний вариант
        return variants[-1]["id"]
```

### `stats_engine.py`

```python
import math
from dataclasses import dataclass


@dataclass
class VariantStats:
    variant_id: str
    sent: int
    positive_replied: int
    replied: int
    meetings_booked: int
    primary_metric_value: float
    confidence_interval: tuple[float, float]


@dataclass
class ExperimentResult:
    variants: list[VariantStats]
    winner_variant_id: str | None
    is_significant: bool
    p_value: float | None
    reason: str


class StatsEngine:
    """Статистический движок для A/B.

    Использует two-proportion z-test для сравнения двух вариантов.
    Для >2 вариантов — попарно, с Bonferroni-коррекцией.
    """

    def __init__(self, *, confidence_level: float = 0.95) -> None:
        self._confidence_level = confidence_level

    def compute(
        self,
        *,
        variants_data: list[dict],
        primary_metric: str,
        sample_size_per_variant: int,
        minimum_detectable_effect: float,
    ) -> ExperimentResult:
        """variants_data: [{variant_id, sent, positive_replied, replied, meetings_booked}]."""
        # Считаем метрику для каждого варианта
        stats = []
        for v in variants_data:
            sent = v["sent"]
            metric_value = self._metric_value(v, primary_metric)
            ci = self._wilson_ci(
                successes=self._metric_successes(v, primary_metric),
                total=sent,
            )
            stats.append(VariantStats(
                variant_id=v["variant_id"],
                sent=sent,
                positive_replied=v.get("positive_replied", 0),
                replied=v.get("replied", 0),
                meetings_booked=v.get("meetings_booked", 0),
                primary_metric_value=metric_value,
                confidence_interval=ci,
            ))

        # Проверяем, достаточно ли данных
        if all(s.sent < sample_size_per_variant for s in stats):
            return ExperimentResult(
                variants=stats, winner_variant_id=None,
                is_significant=False, p_value=None,
                reason=f"Недостаточно данных: нужно по {sample_size_per_variant} на вариант",
            )

        # Сортируем по метрике
        stats.sort(key=lambda s: s.primary_metric_value, reverse=True)
        best = stats[0]

        # Сравниваем с остальными
        if len(stats) == 1:
            return ExperimentResult(
                variants=stats, winner_variant_id=best.variant_id,
                is_significant=False, p_value=None,
                reason="Один вариант — нечего сравнивать",
            )

        # Two-proportion z-test с Bonferroni
        n_comparisons = len(stats) - 1
        corrected_alpha = (1 - self._confidence_level) / n_comparisons

        all_significant = True
        min_p_value = 1.0
        for other in stats[1:]:
            p = self._two_proportion_z_test(
                successes1=self._metric_successes_by_stats(best, primary_metric),
                total1=best.sent,
                successes2=self._metric_successes_by_stats(other, primary_metric),
                total2=other.sent,
            )
            min_p_value = min(min_p_value, p)
            if p >= corrected_alpha:
                all_significant = False

        # Проверяем MDE
        if all_significant and stats[1].sent > 0:
            relative_lift = (best.primary_metric_value - stats[1].primary_metric_value) / max(stats[1].primary_metric_value, 1e-9)
            if abs(relative_lift) < minimum_detectable_effect:
                all_significant = False

        return ExperimentResult(
            variants=stats,
            winner_variant_id=best.variant_id if all_significant else None,
            is_significant=all_significant,
            p_value=min_p_value,
            reason=(
                f"Значимо (p={min_p_value:.4f})" if all_significant
                else f"Не значимо (p={min_p_value:.4f} >= {corrected_alpha:.4f})"
            ),
        )

    def _metric_value(self, v: dict, metric: str) -> float:
        if metric == "reply_rate":
            return v.get("replied", 0) / v["sent"] if v["sent"] else 0.0
        if metric == "positive_reply_rate":
            return v.get("positive_replied", 0) / v["sent"] if v["sent"] else 0.0
        if metric == "meetings_booked":
            return v.get("meetings_booked", 0) / v["sent"] if v["sent"] else 0.0
        if metric == "open_rate":
            return v.get("opened", 0) / v["sent"] if v["sent"] else 0.0
        return 0.0

    def _metric_successes(self, v: dict, metric: str) -> int:
        if metric == "reply_rate":
            return v.get("replied", 0)
        if metric == "positive_reply_rate":
            return v.get("positive_replied", 0)
        if metric == "meetings_booked":
            return v.get("meetings_booked", 0)
        return v.get("opened", 0)

    def _metric_successes_by_stats(self, s: VariantStats, metric: str) -> int:
        if metric == "reply_rate":
            return s.replied
        if metric == "positive_reply_rate":
            return s.positive_replied
        return s.meetings_booked

    def _wilson_ci(self, *, successes: int, total: int) -> tuple[float, float]:
        """Wilson score interval. Работает корректно при малых n."""
        if total == 0:
            return (0.0, 1.0)
        z = 1.96  # для 95%
        p = successes / total
        n = total
        denom = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denom
        margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        return (max(0.0, center - margin), min(1.0, center + margin))

    def _two_proportion_z_test(
        self, *, successes1: int, total1: int, successes2: int, total2: int,
    ) -> float:
        """Двусторонний z-test для двух пропорций. Возвращает p-value."""
        if total1 == 0 or total2 == 0:
            return 1.0
        p1 = successes1 / total1
        p2 = successes2 / total2
        p_pool = (successes1 + successes2) / (total1 + total2)
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / total1 + 1 / total2))
        if se == 0:
            return 1.0
        z = abs(p1 - p2) / se
        # Приближение: p-value = 2 * (1 - Phi(z))
        # Используем простую аппроксимацию для Phi
        p = 2 * (1 - self._normal_cdf(z))
        return max(0.0, min(1.0, p))

    @staticmethod
    def _normal_cdf(z: float) -> float:
        """Аппроксимация CDF нормального распределения."""
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))
```

### Тесты

```python
def test_assigner_deterministic():
    a = VariantAssigner()
    v1 = a.assign(experiment_id="exp1", contact_id="c1", variants=[{"id": "A", "weight": 0.5}, {"id": "B", "weight": 0.5}])
    v2 = a.assign(experiment_id="exp1", contact_id="c1", variants=[{"id": "A", "weight": 0.5}, {"id": "B", "weight": 0.5}])
    assert v1 == v2


def test_assigner_distribution():
    a = VariantAssigner()
    variants = [{"id": "A", "weight": 0.5}, {"id": "B", "weight": 0.5}]
    counts = {"A": 0, "B": 0}
    for i in range(1000):
        v = a.assign(experiment_id="exp1", contact_id=f"c{i}", variants=variants)
        counts[v] += 1
    assert 400 < counts["A"] < 600


def test_stats_significant():
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 500, "positive_replied": 50, "replied": 100},
            {"variant_id": "B", "sent": 500, "positive_replied": 20, "replied": 40},
        ],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert result.is_significant
    assert result.winner_variant_id == "A"


def test_stats_not_significant():
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 500, "positive_replied": 30, "replied": 60},
            {"variant_id": "B", "sent": 500, "positive_replied": 28, "replied": 58},
        ],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert not result.is_significant


def test_stats_insufficient_data():
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 10, "positive_replied": 1, "replied": 2},
            {"variant_id": "B", "sent": 10, "positive_replied": 0, "replied": 1},
        ],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert not result.is_significant
    assert "Недостаточно" in result.reason
```

## Acceptance criteria

```bash
uv run pytest services/experiments-service/tests/test_assigner.py services/experiments-service/tests/test_stats.py -v --cov=experiments_service --cov-report=term-missing
# Ожидание: coverage >= 90%
```

## Подсказки

- **Детерминированное распределение** — критично. Один контакт всегда в одном варианте.
- **Wilson CI** — работает при малых n, в отличие от normal approximation.
- **Bonferroni** — при >2 вариантов. Иначе false positives.
- **MDE** — минимальный эффект, который стоит замечать. Если lift < MDE — не объявляем победителя.

## Анти-паттерны

- ❌ Не использовать `random()` — только детерминированный хеш.
- ❌ Не объявлять победителя без статистической значимости.
- ❌ Не игнорировать MDE.

---

# Задача 4C.3 — ExperimentService + API

**Файл:** `docs/tasks/sprint-4c/4c.3-service.md`

## Детали

### `service.py`

```python
class ExperimentService:
    def __init__(self, repo, analytics_client, publisher, settings) -> None:
        ...

    async def create(self, *, tenant_id: UUID, data: ExperimentCreate, trace_id: str) -> Experiment:
        # Валидация: weights суммируются в 1.0
        variants = data.variants
        total = sum(v.get("weight", 0.0) for v in variants)
        if abs(total - 1.0) > 1e-6:
            raise ValidationError(f"Variants weights must sum to 1.0, got {total}")
        # ... создание
        experiment = Experiment(...)
        await self._repo.add(experiment)
        await emit_experiment_created(self._publisher, experiment, trace_id=trace_id)
        return experiment

    async def start(self, *, tenant_id: UUID, experiment_id: UUID, trace_id: str) -> Experiment:
        exp = await self.get(experiment_id)
        if exp.status != "draft":
            raise ValidationError(f"Cannot start experiment with status {exp.status}")
        exp.status = "running"
        exp.started_at = datetime.now(timezone.utc)
        await self._repo._s.flush()
        return exp

    async def evaluate(self, *, tenant_id: UUID, experiment_id: UUID, trace_id: str) -> Experiment:
        """Считает результаты. Вызывается вручную или по расписанию."""
        exp = await self.get(experiment_id)
        if exp.status not in ("running", "paused"):
            return exp

        # Получаем данные из analytics
        # Для каждого варианта: sent, replied, positive_replied
        variants_data = []
        for v in exp.variants:
            # Запрос в analytics: messages с этим template_id и experiment_id
            stats = await self._analytics.get_experiment_variant_stats(
                tenant_id=tenant_id,
                experiment_id=experiment_id,
                variant_id=v["id"],
            )
            variants_data.append({
                "variant_id": v["id"],
                **stats,
            })

        # Считаем
        engine = StatsEngine(confidence_level=exp.confidence_level)
        result = engine.compute(
            variants_data=variants_data,
            primary_metric=exp.metrics.get("primary", "positive_reply_rate"),
            sample_size_per_variant=exp.sample_size_per_variant,
            minimum_detectable_effect=exp.minimum_detectable_effect,
        )

        exp.results = {
            "variants": [
                {
                    "variant_id": s.variant_id,
                    "sent": s.sent,
                    "replied": s.replied,
                    "positive_replied": s.positive_replied,
                    "meetings_booked": s.meetings_booked,
                    "primary_metric_value": s.primary_metric_value,
                    "confidence_interval": list(s.confidence_interval),
                }
                for s in result.variants
            ],
            "winner_variant_id": result.winner_variant_id,
            "is_significant": result.is_significant,
            "p_value": result.p_value,
            "reason": result.reason,
            "concluded_at": datetime.now(timezone.utc).isoformat() if result.is_significant else None,
        }
        await self._repo._s.flush()

        if result.is_significant and result.winner_variant_id:
            await emit_variant_won(self._publisher, exp, result.winner_variant_id, trace_id=trace_id)
            exp.status = "completed"
            exp.finished_at = datetime.now(timezone.utc)
            await self._repo._s.flush()

        return exp

    async def get_winner_variant(self, *, tenant_id: UUID, experiment_id: UUID) -> str | None:
        """Для composer — какой вариант использовать для этого контакта."""
        exp = await self.get(experiment_id)
        if exp.status != "running":
            return exp.results.get("winner_variant_id")
        # Детерминированное распределение
        assigner = VariantAssigner()
        # contact_id передаётся отдельно — см. API ниже
        ...
```

### API

```python
@router.post("", response_model=ExperimentRead, status_code=201)
async def create_experiment(...): ...


@router.get("", response_model=list[ExperimentSummary])
async def list_experiments(...): ...


@router.get("/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(...): ...


@router.post("/{experiment_id}/start", response_model=ExperimentRead)
async def start_experiment(...): ...


@router.post("/{experiment_id}/pause", response_model=ExperimentRead)
async def pause_experiment(...): ...


@router.post("/{experiment_id}/evaluate", response_model=ExperimentRead)
async def evaluate_experiment(...): ...


@router.post("/{experiment_id}/assign")
async def assign_variant(
    experiment_id: UUID,
    data: AssignRequest,  # {contact_id: UUID}
    svc=Depends(get_service),
) -> dict:
    """Возвращает variant_id для контакта. Используется composer'ом."""
    ...
```

### Интеграция в composer

**Обновить `composer-service`:** при создании Message, если передан `experiment_id`, вызвать experiments-service для получения `variant_id`.

```python
# composer_service/service.py
async def draft(...):
    ...
    experiment = None
    variant_id = data.variant_id
    if data.experiment_id and not variant_id:
        # Запрашиваем у experiments
        variant_id = await self._experiments_client.assign_variant(
            experiment_id=data.experiment_id,
            contact_id=data.contact_id,
            tenant_id=str(tenant_id),
        )
    if data.experiment_id:
        experiment = {
            "experiment_id": str(data.experiment_id),
            "variant_id": variant_id,
            "hypothesis": data.hypothesis,
        }
    ...
```

**Плюс:** если `variant_id` известен, выбрать соответствующий `template_id` из варианта эксперимента.

```python
if experiment and variant_id:
    # Получаем эксперимент и находим вариант
    exp = await self._experiments_client.get_experiment(data.experiment_id, tenant_id=str(tenant_id))
    variant = next((v for v in exp["variants"] if v["id"] == variant_id), None)
    if variant and variant.get("template_id"):
        template = self._templates.get(variant["template_id"])
```

### `events.py`

```python
async def emit_experiment_created(publisher, experiment, *, trace_id): ...
async def emit_variant_won(publisher, experiment, variant_id, *, trace_id): ...
```

**Добавить `EXPERIMENT_CREATED`, `EXPERIMENT_VARIANT_WON` в `nats_client.subjects`** (если ещё нет — они были в Спринте 0).

### Периодический evaluate

В `main.py` — фоновая задача, раз в час вызывает `evaluate` для всех running experiments.

## Acceptance criteria

```bash
# 1. Создать эксперимент
EXP=$(curl -sX POST https://experiments.dev.aitler.ru/experiments \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: exp-1" \
  -d '{
    "name": "Subject test v1",
    "hypothesis": "Вопрос в теме увеличит reply rate",
    "variable_type": "subject",
    "variable_description": "С вопросом vs без",
    "channel": "email",
    "variants": [
      {"id": "A", "name": "Без вопроса", "template_id": "email_cold_outreach", "weight": 0.5},
      {"id": "B", "name": "С вопросом", "template_id": "email_cold_outreach", "weight": 0.5}
    ],
    "metrics": {"primary": "positive_reply_rate", "secondary": ["reply_rate", "bounce_rate"]},
    "sample_size_per_variant": 100
  }')
EXP_ID=$(echo $EXP | jq -r .id)

# 2. Запустить
curl -sX POST https://experiments.dev.aitler.ru/experiments/$EXP_ID/start \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: start-1" | jq .status
# Ожидание: "running"

# 3. Assign variant
curl -sX POST https://experiments.dev.aitler.ru/experiments/$EXP_ID/assign \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: assign-1" \
  -d '{"contact_id": "'$CONTACT_ID'"}' | jq .
# Ожидание: {variant_id: "A" или "B"}

# 4. Evaluate (после накопления данных)
curl -sX POST https://experiments.dev.aitler.ru/experiments/$EXP_ID/evaluate \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: eval-1" | jq '.results | {winner_variant_id, is_significant, p_value}'
# Ожидание: либо "недостаточно данных", либо результат
```

## Подсказки

- **`assign_variant` вызывается composer'ом** при каждом draft, если experiment_id задан.
- **`evaluate` — вручную или по расписанию.** Не автоматически после каждой отправки.
- **Победитель определяется только при статистической значимости.**
- **Детерминированное распределение** — один контакт всегда в одном варианте.

## Анти-паттерны

- ❌ Не использовать `random()` для распределения.
- ❌ Не объявлять победителя без значимости.
- ❌ Не забывать про MDE.

---

# Задача 4C.4 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-4c/4c.4-tests.md`

## Детали

### E2E

1. Создать эксперимент с 2 вариантами.
2. Запустить.
3. Симулировать 200 сообщений с распределением по вариантам.
4. Симулировать replies.
5. Вызвать evaluate.
6. Проверить winner (если значимо).

### CI

Добавить `experiments-service` в matrix.

## Acceptance criteria

```bash
uv run pytest services/experiments-service/tests/ -v --cov=experiments_service --cov-report=term-missing
# Ожидание: coverage >= 85%
```

---

## Финальная E2E-проверка Спринта 4

```bash
export TENANT="<sandbox>"
export MSG_ID="<id письма из Спринта 3>"
export CONTACT_ID="<contact_id>"

# 1. Симулировать reply через NATS
docker run --rm --network outreach-net natsio/nats-box:0.16.0 \
  nats -s "nats://$NATS_USER:$NATS_PASSWORD@nats:4222" pub "reply.received.$TENANT" \
  '{"event_type":"reply.received","schema_version":"1.0","occurred_at":"2026-10-02T10:00:00Z","tenant_id":"'$TENANT'","trace_id":"e2e-r1","producer":"test/0.1","payload":{"message_id":"'$MSG_ID'","from_email":"ivan@example.com","from_name":"Иван","subject":"Re: Предложение","body":"Интересно, расскажите подробнее. Какая цена?","received_at":"2026-10-02T10:00:00Z","in_reply_to":"<...>","references":"","message_id_header":"<...>"}}'

# 2. Дождаться классификации
sleep 5
curl -s -H "X-Tenant-ID: $TENANT" "https://reply-classifier.dev.aitler.ru/?message_id=$MSG_ID" | jq '.[0] | {category, classification_confidence, suggested_action: .suggested_next_action.action}'
# Ожидание: category="question", action="reply"

# 3. Message обновлён
curl -s -H "X-Tenant-ID: $TENANT" https://composer.dev.aitler.ru/messages/$MSG_ID | jq '.status, .engagement.replied_at'
# Ожидание: "replied", timestamp

# 4. Contact обновлён
curl -s -H "X-Tenant-ID: $TENANT" https://contact-store.dev.aitler.ru/contacts/$CONTACT_ID | jq '.replied_positive, .last_reply_at'
# Ожидание: true, timestamp

# 5. Analytics: refresh + overview
# Ждём 5 минут или принудительно:
bash scripts/psql.sh -c "REFRESH MATERIALIZED VIEW analytics.mv_daily_reply_metrics;"
curl -s -H "X-Tenant-ID: $TENANT" "https://analytics.dev.aitler.ru/reply-categories?from_date=2026-09-01&to_date=2026-10-02" | jq .
# Ожидание: question: 1

curl -s -H "X-Tenant-ID: $TENANT" https://analytics.dev.aitler.ru/funnel | jq .
# Ожидание: funnel с replied >= 1

# 6. Создать эксперимент
EXP_ID=$(curl -sX POST https://experiments.dev.aitler.ru/experiments \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-exp1" \
  -d '{"name":"E2E test","hypothesis":"Тест","variable_type":"subject","variable_description":"","channel":"email","variants":[{"id":"A","name":"A","template_id":"email_cold_outreach","weight":0.5},{"id":"B","name":"B","template_id":"email_cold_outreach","weight":0.5}],"metrics":{"primary":"positive_reply_rate"},"sample_size_per_variant":10}' | jq -r .id)

curl -sX POST https://experiments.dev.aitler.ru/experiments/$EXP_ID/start \
  -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: e2e-start1" | jq .status
# Ожидание: "running"

# 7. Assign
curl -sX POST https://experiments.dev.aitler.ru/experiments/$EXP_ID/assign \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-assign1" \
  -d '{"contact_id": "'$CONTACT_ID'"}' | jq .
# Ожидание: {variant_id: "A"|"B"}

# 8. Evaluate (недостаточно данных)
curl -sX POST https://experiments.dev.aitler.ru/experiments/$EXP_ID/evaluate \
  -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: e2e-eval1" | jq '.results.is_significant, .results.reason'
# Ожидание: false, "Недостаточно данных"

# 9. События
bash scripts/nats-cli.sh stream view BRIEFS --last 30 | grep -E "reply\.(received|classified)|experiment\."
# Ожидание: все

# 10. RLS
OTHER="00000000-0000-0000-0000-000000000000"
curl -s -H "X-Tenant-ID: $OTHER" https://analytics.dev.aitler.ru/funnel | jq .
# Ожидание: пустой funnel (не данные другого тенанта)

# 11. CI
git push origin develop
# Зелёные
```

**Если все 11 пунктов проходят — Спринт 4 закрыт.**

---

## Проверка: что я перепроверил

- [x] Порядок задач: 4A.1 → 4A.2 → 4A.3 → 4A.4 → 4A.5 → 4B.1 → 4B.2 → 4B.3 → 4B.4 → 4C.1 → 4C.2 → 4C.3 → 4C.4, зависимости соблюдены.
- [x] Reply-классификатор: rule-fallback → LLM. Rule обрабатывает очевидное, LLM — остальное.
- [x] Автоматическая отписка при `UNSUBSCRIBE` — критично для репутации.
- [x] Дедуп по `(message_id, from_email)`.
- [x] Расширение `reply.received` события в sender-email (передача body).
- [x] Новый endpoint `PATCH /contacts/{id}/outreach-history` в contact-store.
- [x] Analytics: MV в схеме `analytics`, read-only, refresh раз в 5 минут.
- [x] Alert engine: раз в час, только при достаточной выборке.
- [x] Experiments: детерминированное распределение через хеш.
- [x] StatsEngine: two-proportion z-test + Wilson CI + Bonferroni.
- [x] MDE учитывается.
- [x] Интеграция experiments в composer (assign_variant).
- [x] RLS на всех таблицах.
- [x] События: reply.classified, analytics.alert, experiment.created, experiment.variant_won.
- [x] Mypy strict, ruff, pytest.
- [x] Никаких cross-service импортов.
- [x] Idempotency-Key на всех POST.
- [x] Кэш метрик в Redis (60 секунд).
- [x] Никаких `print`, `time.sleep`, `datetime.utcnow`.

---

## Что дальше (Спринт 5)

После закрытия Спринта 4 система **функционально полная**: Brief → ICP → sourcing → composer → review → sender → reply → analytics → experiments.

**Спринт 5** — это **orchestrator + auto-revision + Telegram/WhatsApp senders**. Плюс возможные улучшения:
- Orchestrator, который автоматически связывает шаги через события.
- Auto-revision: если reply rate низкий — система сама предлагает переписать оффер.
- Мульти-armed bandit для экспериментов.
- Telegram/WhatsApp senders (каналы).
- LinkedIn sender (рискованный, отдельно).

**Что от тебя нужно сейчас:**
1. Разложить эти 14 задач по файлам в `docs/tasks/sprint-4/` (4A, 4B, 4C — три подпапки).
2. Дать агенту: «Начинай с 4A.1. 4A — обязательно до конца (классификация), потом 4B (метрики), потом 4C (эксперименты)».
3. Сообщить мне, когда Спринт 4 закрыт (или если агент застрял — особенно на 4B.1, там materialized views).

**Критичный вопрос к тебе:**
- **Расширение `reply.received` события** — нужно вернуться в `sender-email` и обновить `emit_reply_received` (передавать body). Это изменение Спринта 3, но необходимое. Если ты хочешь избежать изменения — можно сделать так: reply-classifier сам забирает тело через IMAP. Но это дублирование IMAP-логики. **Рекомендую расширить событие.**

Если хочешь что-то поправить сейчас — скажи.
