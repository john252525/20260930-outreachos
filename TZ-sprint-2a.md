# Спринт 2A — `contact-store`

Проверил: зависимости от Спринта 0 и 1 соблюдены, порядок задач логичен, acceptance criteria проверяемы, RLS корректен, дедуп детерминированный, нет противоречий с `docs/contracts.md`. Каждая задача самодостаточна.

## Что такое `contact-store` и почему он критичен

Это **единственный источник правды** по компаниям и контактам. Все остальные сервисы (sourcing, composer, reply-classifier, analytics) будут читать и писать сюда. Если модель данных кривая или дедуп плохой — мусор расползётся по всей платформе и его будет больно чистить.

**Ключевые принципы:**
1. **Дедуп детерминированный.** Никаких «похоже на то» на этом этапе. Только точные fingerprints.
2. **Upsert, не insert.** Sourcing будет совать одно и то же по десять раз — store должен мержить, не плодить дубликаты.
3. **Evidence сохраняется.** Каждое поле имеет `confidence` и `evidence`. Merge — по правилу «побеждает evidence с большей confidence».
4. **История аккумулируется.** `signals`, `outreach_history` — не перезаписываются, а дополняются.
5. **Stop-list проверяется до записи.** Если email в блок-листе — контакт не создаётся.

## Архитектура сервиса

```
                    ┌──────────────────────────────────────┐
                    │           contact-store              │
                    │                                       │
   HTTP requests ──►│  API layer (routes)                   │
                    │       │                               │
                    │       ▼                               │
                    │  CompanyService / ContactService      │
                    │       │                               │
                    │       ├──► Fingerprint (pure)         │
                    │       ├──► Merger (pure + DB)         │
                    │       ├──► StopList (DB)              │
                    │       └──► Repository (SQLAlchemy)    │
                    │                                       │
                    │  Events:                              │
                    │   - contact.created                   │
                    │   - contact.updated                   │
                    │   - contact.merged                    │
                    │   - contact.unsubscribed              │
                    │   - company.created                   │
                    │   - company.updated                   │
                    │   - company.merged                    │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                                   Postgres
```

**Что НЕ делает (осознанно):**
- Не ходит в интернет (это sourcing).
- Не вызывает LLM (кроме, может, fuzzy-match в будущем — но не в 2A).
- Не генерирует письма (это composer).
- Не считает метрики (это analytics).

**Модель данных:** Company и Contact — отдельные сущности в одной БД, в одном сервисе, но с разными таблицами. Связь: `Contact.company_id → Company.id` (nullable — бывают контакты без компании).

---

# Задача 2A.1 — Каркас `contact-store` + модели Company/Contact

**Файл:** `docs/tasks/sprint-2a/2a.1-bootstrap.md`

## Цель

Создать каркас сервиса по образцу `brief-service`, определить SQLAlchemy-модели `Company` и `Contact` со всеми полями из `docs/contracts.md`, сделать миграции с RLS. Сервис поднимается, healthcheck зелёный, таблицы созданы.

## Зависимости

Спринт 0 и 1 закрыты.

## Что создать

```
services/contact-store/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_companies_contacts.py
├── src/contact_store/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py                     # Company, Contact, CompanyEmail, ContactEmail, ContactPhone
│   ├── schemas.py                    # API-схемы
│   ├── repository.py                 # CompanyRepository, ContactRepository
│   ├── fingerprint.py                # pure functions
│   ├── merger.py                     # merge logic
│   ├── stoplist.py                   # stoplist logic
│   ├── service.py                    # CompanyService, ContactService
│   ├── events.py
│   └── api/
│       ├── __init__.py
│       ├── routes_companies.py
│       ├── routes_contacts.py
│       ├── routes_stoplist.py
│       └── deps.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_fingerprint.py
    ├── test_merger.py
    ├── test_companies_api.py
    ├── test_contacts_api.py
    └── test_stoplist.py
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "contact-store"
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
    "python-stdnum>=1.20",          # для нормализации ИНН/ОГРН
    "common",
    "contracts",
    "db",
    "nats-client",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/contact_store"]
```

**`python-stdnum`** — для валидации и нормализации ИНН/ОГРН. Добавляем сразу, пригодится.

### `config.py`

```python
from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field("contact-store", alias="SERVICE_NAME")

    # Дедуп
    enable_fuzzy_company_match: bool = Field(False, alias="CONTACT_STORE_FUZZY_MATCH")
    # Пока false. Включим в 2C или позже.

    # Stop-list
    global_stoplist_enabled: bool = Field(True, alias="CONTACT_STORE_GLOBAL_STOPLIST")

    # Bulk
    bulk_max_size: int = Field(500, alias="CONTACT_STORE_BULK_MAX")
```

### `models.py`

Ключевой файл. Модели должны точно соответствовать `docs/contracts.md` разделы 3 и 4.

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
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


class Company(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "companies"

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)

    # Денормализованные «горячие» поля для поиска (в дополнение к JSONB)
    name_normalized: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    domain_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    ogrn: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)

    # Остальное — JSONB, по контракту
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Денормализованные для быстрого доступа
    contacts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_companies_tenant_fingerprint"),
        Index("ix_companies_tenant_status", "tenant_id", "status"),
        Index("ix_companies_tenant_created", "tenant_id", "created_at"),
        Index("ix_companies_payload_gin", "payload", postgresql_using="gin", postgresql_ops={"payload": "jsonb_path_ops"}),
    )

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")


class Contact(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "contacts"

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)

    # Денормализованные «горячие» поля
    full_name_normalized: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    primary_phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    role_category: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    seniority: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")

    # Остальное — JSONB
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Outreach
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_positive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_contacts_tenant_fingerprint"),
        Index("ix_contacts_tenant_status", "tenant_id", "status"),
        Index("ix_contacts_tenant_created", "tenant_id", "created_at"),
        Index("ix_contacts_company", "company_id"),
        Index("ix_contacts_payload_gin", "payload", postgresql_using="gin", postgresql_ops={"payload": "jsonb_path_ops"}),
    )

    company: Mapped[Company | None] = relationship(back_populates="contacts")


class ContactEmail(Base, UUIDPrimaryKeyMixin, TenantMixin):
    """Вынесенная таблица emails для быстрого поиска и дедупа."""
    __tablename__ = "contact_emails"

    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(320), nullable=False)  # normalized lowercase
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_contact_emails_tenant_value", "tenant_id", "value"),
        UniqueConstraint("tenant_id", "value", name="uq_contact_emails_tenant_value"),
    )


class ContactPhone(Base, UUIDPrimaryKeyMixin, TenantMixin):
    """Вынесенная таблица телефонов."""
    __tablename__ = "contact_phones"

    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(20), nullable=False)  # E.164
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_contact_phones_tenant_value", "tenant_id", "value"),
        UniqueConstraint("tenant_id", "value", name="uq_contact_phones_tenant_value"),
    )


class StopListEntry(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Записи stop-листа. Глобальные имеют tenant_id = null."""
    __tablename__ = "stoplist_entries"

    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # "global" | "tenant"
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # "email" | "phone" | "domain"
    value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)  # normalized
    reason: Mapped[str] = mapped_column(String(64), nullable=False)  # "unsubscribed" | "bounced_hard" | "complained" | "manual" | "disqualified"
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")

    __table_args__ = (
        UniqueConstraint("scope", "tenant_id", "kind", "value", name="uq_stoplist_entry"),
        Index("ix_stoplist_lookup", "kind", "value"),
    )
```

**Важно:**
- `tenant_id` для глобальных записей stop-list — `NULL`. Это единственное исключение из правила «всегда есть tenant_id». Обосновано: глобальные записи не принадлежат ни одному тенанту. RLS для этой таблицы настраивается особо (см. миграцию).
- `payload` JSONB — соответствует контракту. Денормализованные поля (`name_normalized`, `domain_normalized`, `inn`, `ogrn`, `primary_email`, `primary_phone`) вынесены для индексов и быстрого поиска.
- `ContactEmail` и `ContactPhone` — вынесены, потому что по ним ищут и дедуплицируют. Хранить их в JSONB и искать GIN'ом — медленно.
- **`UniqueConstraint("tenant_id", "value")`** для email и phone — гарантия, что один email не привязан к двум контактам в рамках тенанта. Это критично для дедупа.

### `migrations/versions/0001_create_companies_contacts.py`

Полная миграция со всеми таблицами. RLS — на каждой:

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_create_companies_contacts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- companies ---
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("name_normalized", sa.String(512), nullable=False),
        sa.Column("domain_normalized", sa.String(255), nullable=True),
        sa.Column("inn", sa.String(12), nullable=True),
        sa.Column("ogrn", sa.String(15), nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("contacts_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_companies_tenant_fingerprint", "companies", ["tenant_id", "fingerprint"], unique=True)
    op.create_index("ix_companies_tenant_status", "companies", ["tenant_id", "status"])
    op.create_index("ix_companies_tenant_created", "companies", ["tenant_id", "created_at"])
    op.create_index("ix_companies_name_norm", "companies", ["name_normalized"])
    op.create_index("ix_companies_domain_norm", "companies", ["domain_normalized"])
    op.create_index("ix_companies_inn", "companies", ["inn"])
    op.create_index("ix_companies_ogrn", "companies", ["ogrn"])
    op.execute("CREATE INDEX ix_companies_payload_gin ON companies USING gin (payload jsonb_path_ops)")

    # --- contacts ---
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("full_name_normalized", sa.String(512), nullable=False),
        sa.Column("primary_email", sa.String(320), nullable=True),
        sa.Column("primary_phone", sa.String(20), nullable=True),
        sa.Column("role_category", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("seniority", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_positive", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contacts_tenant_fingerprint", "contacts", ["tenant_id", "fingerprint"], unique=True)
    op.create_index("ix_contacts_tenant_status", "contacts", ["tenant_id", "status"])
    op.create_index("ix_contacts_tenant_created", "contacts", ["tenant_id", "created_at"])
    op.create_index("ix_contacts_company", "contacts", ["company_id"])
    op.create_index("ix_contacts_name_norm", "contacts", ["full_name_normalized"])
    op.create_index("ix_contacts_primary_email", "contacts", ["primary_email"])
    op.create_index("ix_contacts_primary_phone", "contacts", ["primary_phone"])
    op.execute("CREATE INDEX ix_contacts_payload_gin ON contacts USING gin (payload jsonb_path_ops)")

    # --- contact_emails ---
    op.create_table(
        "contact_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.String(320), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.create_index("ix_contact_emails_tenant_value", "contact_emails", ["tenant_id", "value"], unique=True)
    op.create_index("ix_contact_emails_contact", "contact_emails", ["contact_id"])

    # --- contact_phones ---
    op.create_table(
        "contact_phones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.String(20), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_whatsapp", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_telegram", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.create_index("ix_contact_phones_tenant_value", "contact_phones", ["tenant_id", "value"], unique=True)
    op.create_index("ix_contact_phones_contact", "contact_phones", ["contact_id"])

    # --- stoplist_entries ---
    op.create_table(
        "stoplist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stoplist_lookup", "stoplist_entries", ["kind", "value"])
    op.create_index("ix_stoplist_tenant", "stoplist_entries", ["tenant_id"])

    # Уникальность с учётом NULL (tenant_id может быть NULL для global)
    op.execute("""
        CREATE UNIQUE INDEX uq_stoplist_entry
        ON stoplist_entries (scope, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), kind, value)
    """)

    # --- RLS ---
    for table, column in [
        ("companies", "tenant_id"),
        ("contacts", "tenant_id"),
        ("contact_emails", "tenant_id"),
        ("contact_phones", "tenant_id"),
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({column} = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK ({column} = current_setting('app.tenant_id', true)::uuid)
        """)

    # Stoplist — особая логика: видим global + tenant-скоуп
    op.execute("ALTER TABLE stoplist_entries ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY stoplist_entries_isolation ON stoplist_entries
        USING (
            tenant_id IS NULL
            OR tenant_id = current_setting('app.tenant_id', true)::uuid
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
    """)
    # USING: SELECT/UPDATE/DELETE — видим global + свои
    # WITH CHECK: INSERT/UPDATE — только свои (global создаётся системной ролью)


def downgrade() -> None:
    for table in ["contact_phones", "contact_emails", "contacts", "companies", "stoplist_entries"]:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"DROP POLICY IF EXISTS stoplist_entries_isolation ON {table}")
    op.drop_table("stoplist_entries")
    op.drop_table("contact_phones")
    op.drop_table("contact_emails")
    op.drop_table("contacts")
    op.drop_table("companies")
```

**Важно про stoplist RLS:**
- `USING (tenant_id IS NULL OR tenant_id = current_setting(...))` — читаем глобальные + свои.
- `WITH CHECK (tenant_id = current_setting(...))` — вставлять можно только свои (не NULL). Глобальные создаются отдельной системной ролью или через миграцию.

**Важно про глобальный stoplist:** если тенант хочет добавить запись «в глобальный» — это не его право. Только через админский эндпоинт, который мы добавим позже (с отдельной ролью). В 2A — только тенант-скоупный + предзаполненные глобальные из миграции (например, тестовые).

### `main.py`

По образцу `brief-service.main`. Отличия:
- Свой `Settings`.
- Роутеры: `companies`, `contacts`, `stoplist`.
- `LLMClient` не нужен.
- `Publisher` — нужен для событий.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  contact-store:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/contact-store/Dockerfile
    container_name: outreach-contact-store
    environment:
      <<: *common-env
      SERVICE_NAME: contact-store
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/3
      CONTACT_STORE_FUZZY_MATCH: "false"
      CONTACT_STORE_GLOBAL_STOPLIST: "true"
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      caddy: contact-store.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

### Обновить `scripts/migrate.sh`

Добавить `contact-store` в `SERVICES_WITH_DB`.

### `Dockerfile`

Скопировать из `brief-service/Dockerfile`, поменять `--package contact-store` и `CMD`.

## Acceptance criteria

```bash
# 1. Миграция применяется
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm contact-store alembic upgrade head
# Ожидание: Applying 0001_create_companies_contacts... OK

# 2. Сервис поднимается
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d contact-store
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev logs --tail=20 contact-store
# Ожидание: service_started

# 3. Healthcheck
curl -fsS https://contact-store.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

# 4. Таблицы созданы
bash scripts/psql.sh -c "\dt"
# Ожидание: companies, contacts, contact_emails, contact_phones, stoplist_entries

# 5. RLS включён
bash scripts/psql.sh -c "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename IN ('companies','contacts','contact_emails','contact_phones','stoplist_entries');"
# Ожидание: rowsecurity = true для всех

# 6. Политики
bash scripts/psql.sh -c "SELECT tablename, policyname FROM pg_policies WHERE schemaname='public';"
# Ожидание: 5 политик

# 7. OpenAPI
curl -fsS https://contact-store.dev.aitler.ru/openapi.json | jq '.info.title'
# Ожидание: "Contact Store"
```

## Подсказки

- **Денормализация** — осознанный компромисс. `name_normalized`, `domain_normalized`, `primary_email`, `primary_phone` дублируются в JSONB и в колонках. При обновлении payload — синхронизировать и колонки. Это делается в `repository.py`, не в модели.
- **`ContactEmail`/`ContactPhone`** — вынесены из JSONB. Да, есть дублирование с `payload.emails`, но это цена за быстрый поиск и уникальность. Синхронизация — в `repository.upsert_contact`.
- **`python-stdnum`** — для валидации ИНН (10 или 12 цифр с контрольной суммой) и ОГРН (13 или 15 цифр). Использовать в `fingerprint.py`.
- **GIN-индексы** по `payload` — на будущее (поиск по тегам, signals). На dev можно опустить, но лучше сразу.
- **`uq_stoplist_entry`** — COALESCE на NULL, потому что уникальный индекс в Postgres игнорирует NULL. Так global (tenant_id=NULL) и tenant-скоупные записи с одинаковым value не конфликтуют, но tenant-скоупные между собой — да.

## Анти-паттерны

- ❌ Не хранить emails/phones только в JSONB — иначе дедуп будет медленным.
- ❌ Не забыть `COALESCE` в unique-индексе stoplist.
- ❌ Не забыть RLS на новые таблицы.
- ❌ Не делать `tenant_id NOT NULL` для stoplist — глобальные записи имеют NULL.
- ❌ Не забывать синхронизировать денормализованные поля при upsert.

---

# Задача 2A.2 — Fingerprint (детерминированный дедуп)

**Файл:** `docs/tasks/sprint-2a/2a.2-fingerprint.md`

## Цель

Реализовать чистые функции нормализации и fingerprints для компаний и контактов. Плюс нормализацию email, phone, домена, названий.

## Зависимости

2A.1.

## Что создать

```
services/contact-store/src/contact_store/
├── normalization.py
└── fingerprint.py

services/contact-store/tests/
├── test_normalization.py
└── test_fingerprint.py
```

## Детали реализации

### `normalization.py`

```python
import re
import unicodedata

from stdnum.ru import inn as ru_inn, ogrn as ru_ogrn


_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^\w\s\-]", re.UNICODE)
_LEGAL_SUFFIXES = {
    "ооо", "оао", "зао", "пао", "ип", "нко", "ано", "ао",
    "llc", "ltd", "inc", "corp", "corporation", "co", "company",
    "gmbh", "ag", "sa", "sas", "sarl", "bv", "nv", "plc",
    "limited", "group", "holdings",
}


def normalize_whitespace(s: str) -> str:
    return _WS_RE.sub(" ", s.strip())


def normalize_company_name(name: str) -> str:
    """Нормализует название компании для fingerprint.

    - lowercase
    - убирает ООО/LLC/Inc и т.п. (в начале и в конце)
    - убирает лишние знаки
    - схлопывает пробелы
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower()
    # Убираем кавычки разных видов
    s = s.replace("«", "").replace("»", "").replace('"', "").replace("'", "")
    s = _NON_ALNUM_RE.sub(" ", s)
    s = normalize_whitespace(s)

    # Убираем legal-суффиксы с начала и конца
    tokens = s.split()
    while tokens and tokens[0] in _LEGAL_SUFFIXES:
        tokens.pop(0)
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_domain(domain: str | None) -> str | None:
    """example.com, www.example.com, https://example.com/path → example.com."""
    if not domain:
        return None
    s = domain.strip().lower()
    # Убираем схему
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    # Убираем путь
    s = s.split("/", 1)[0]
    # Убираем www.
    if s.startswith("www."):
        s = s[4:]
    # Убираем порт
    s = s.split(":", 1)[0]
    if not s or "." not in s:
        return None
    return s


def normalize_email(email: str | None) -> str | None:
    """lowercase, strip. Gmail-специфика (точки) — НЕ трогаем."""
    if not email:
        return None
    s = email.strip().lower()
    if "@" not in s:
        return None
    return s


def normalize_phone(phone: str | None, default_country: str = "RU") -> str | None:
    """Приводит к E.164. Для РФ: +7XXXXXXXXXX. Для остальных — как есть с +."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None

    if default_country == "RU":
        if len(digits) == 11 and digits[0] in ("7", "8"):
            return "+7" + digits[1:]
        if len(digits) == 10:
            return "+7" + digits
        if digits.startswith("7") and len(digits) == 11:
            return "+" + digits

    # Fallback: если начинается с +, оставляем
    if phone.strip().startswith("+"):
        return "+" + digits
    return "+" + digits


def normalize_person_name(name: str) -> str:
    """lowercase, схлопывает пробелы, убирает точки в инициалах."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower()
    s = s.replace(".", " ")
    s = _NON_ALNUM_RE.sub(" ", s)
    return normalize_whitespace(s)


def normalize_inn(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if ru_inn.is_valid(digits):
        return digits
    return None


def normalize_ogrn(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if ru_ogrn.is_valid(digits):
        return digits
    return None
```

**Важно:** `normalize_phone` — упрощённый. Для не-РФ номеров нужен `phonenumbers` (Google libphonenumber). На 2A — только РФ, для остальных fallback. Позже можно прикрутить полноценный.

### `fingerprint.py`

```python
import hashlib


def _hash(parts: list[str]) -> str:
    payload = "|".join(p or "" for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def company_fingerprint(
    *,
    name_normalized: str,
    domain_normalized: str | None,
    inn: str | None = None,
) -> str:
    """Fingerprint компании.

    Приоритет:
    1. ИНН — самый надёжный (уникален для юрлица).
    2. Домен — если сайт есть.
    3. Нормализованное имя — fallback.
    """
    if inn:
        return _hash(["inn", inn])
    if domain_normalized:
        return _hash(["domain", domain_normalized])
    if name_normalized:
        return _hash(["name", name_normalized])
    raise ValueError("Cannot compute fingerprint: no inn, domain, or name")


def contact_fingerprint(
    *,
    email: str | None,
    phone: str | None,
    full_name_normalized: str,
    company_domain: str | None,
) -> str:
    """Fingerprint контакта.

    Приоритет:
    1. Email.
    2. Phone.
    3. Имя + домен компании.
    """
    if email:
        return _hash(["email", email])
    if phone:
        return _hash(["phone", phone])
    if full_name_normalized and company_domain:
        return _hash(["name+domain", full_name_normalized, company_domain])
    if full_name_normalized:
        raise ValueError(
            "Cannot compute contact fingerprint: name without company domain is too weak"
        )
    raise ValueError("Cannot compute fingerprint: no email, phone, or name+domain")
```

**Важно:** контакт без email, phone и без компании — не создаём. Слишком велик риск, что это дубликат. Это осознанное ограничение.

### Тесты

`tests/test_normalization.py` — покрыть все функции:

```python
import pytest
from contact_store.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_person_name,
    normalize_inn,
)


@pytest.mark.parametrize("raw,expected", [
    ("ООО «Ромашка»", "ромашка"),
    ("Ромашка LLC", "ромашка"),
    ("  ЗАО   Ромашка  ", "ромашка"),
    ('ООО "Ромашка-М"', "ромашка-м"),
    ("Romashka Inc.", "romashka"),
    ("", ""),
    ("ООО", ""),
])
def test_normalize_company_name(raw, expected):
    assert normalize_company_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("https://www.example.com/path", "example.com"),
    ("http://example.com", "example.com"),
    ("Example.COM", "example.com"),
    ("example.com:8080", "example.com"),
    ("", None),
    (None, None),
    ("not-a-domain", None),
])
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("John@Example.COM", "john@example.com"),
    ("  x@y.z  ", "x@y.z"),
    ("invalid", None),
    ("", None),
])
def test_normalize_email(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("+7 900 123-45-67", "+79001234567"),
    ("8 (900) 123-45-67", "+79001234567"),
    ("9001234567", "+79001234567"),
    ("+7-900-123-45-67", "+79001234567"),
    ("", None),
])
def test_normalize_phone_ru(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Иван Петров", "иван петров"),
    ("И. Петров", "и петров"),
    ("  Иван   Петров  ", "иван петров"),
])
def test_normalize_person_name(raw, expected):
    assert normalize_person_name(raw) == expected


def test_normalize_inn_valid():
    # Валидный ИНН юрлица (10 цифр, с корректной контрольной суммой)
    assert normalize_inn("7707083893") == "7707083893"


def test_normalize_inn_invalid():
    assert normalize_inn("1234567890") is None
    assert normalize_inn("abc") is None
    assert normalize_inn("") is None
```

**Важно:** тестовые ИНН должны быть валидными. `7707083893` — ИНН Сбербанка, валиден. Использовать реальные валидные ИНН в тестах.

`tests/test_fingerprint.py`:

```python
import pytest
from contact_store.fingerprint import company_fingerprint, contact_fingerprint


def test_company_fingerprint_priorities():
    fp_inn = company_fingerprint(name_normalized="x", domain_normalized="x.com", inn="7707083893")
    fp_domain = company_fingerprint(name_normalized="x", domain_normalized="x.com")
    fp_name = company_fingerprint(name_normalized="x", domain_normalized=None)
    assert fp_inn != fp_domain != fp_name


def test_company_fingerprint_deterministic():
    fp1 = company_fingerprint(name_normalized="x", domain_normalized="x.com")
    fp2 = company_fingerprint(name_normalized="x", domain_normalized="x.com")
    assert fp1 == fp2


def test_company_fingerprint_requires_something():
    with pytest.raises(ValueError):
        company_fingerprint(name_normalized="", domain_normalized=None)


def test_contact_fingerprint_priorities():
    fp_email = contact_fingerprint(email="a@b.com", phone=None, full_name_normalized="x", company_domain="x.com")
    fp_phone = contact_fingerprint(email=None, phone="+79001234567", full_name_normalized="x", company_domain="x.com")
    fp_name = contact_fingerprint(email=None, phone=None, full_name_normalized="x", company_domain="x.com")
    assert fp_email != fp_phone != fp_name


def test_contact_fingerprint_name_without_domain_raises():
    with pytest.raises(ValueError):
        contact_fingerprint(email=None, phone=None, full_name_normalized="x", company_domain=None)
```

## Acceptance criteria

```bash
uv run pytest services/contact-store/tests/test_normalization.py services/contact-store/tests/test_fingerprint.py -v --cov=contact_store.normalization --cov=contact_store.fingerprint --cov-report=term-missing
# Ожидание: coverage >= 95%, все passed

uv run mypy services/contact-store
uv run ruff check services/contact-store
```

## Подсказки

- **Fingerprint стабилен.** Если поменяешь алгоритм — все существующие fingerprints станут невалидными. Версионируй: `v1:sha256...`. Пока не нужно, но помни.
- **`normalize_company_name`** должен быть **идемпотентен**: `f(f(x)) == f(x)`.
- **ИНН-валидация** — через `stdnum.ru.inn.is_valid`. Если невалиден — возвращаем `None`, не «как есть».
- **Один и тот же email в разных тенантах** — это разные контакты. Fingerprint не включает tenant_id, но уникальный индекс — включает. Это правильно: fingerprint глобальный, но запись тенант-скоупная.

## Анти-паттерны

- ❌ Не использовать `lower()` без `unicodedata.normalize("NFKC")` — кириллица и латиница могут выглядеть одинаково.
- ❌ Не игнорировать пробелы/знаки в названиях.
- ❌ Не использовать нестабильные хэши (например, `hash()` в Python — не стабилен между процессами).
- ❌ Не делать fingerprint зависимым от tenant_id.
- ❌ Не создавать контакт без email/phone/company.

---

# Задача 2A.3 — Merger (слияние дубликатов)

**Файл:** `docs/tasks/sprint-2a/2a.3-merger.md`

## Цель

Реализовать логику слияния двух компаний и двух контактов при совпадении fingerprint. Правила: evidence с большей confidence побеждает, история аккумулируется, primary выбирается по confidence.

## Зависимости

2A.1, 2A.2.

## Что создать

```
services/contact-store/src/contact_store/
└── merger.py

services/contact-store/tests/
└── test_merger.py
```

## Детали реализации

### `merger.py`

```python
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def _merge_fact(existing: dict | None, incoming: dict | None) -> dict | None:
    """Сливает два fact-объекта {value, confidence, evidence}.

    Правила:
    - Если один None — возвращаем другой.
    - Если confidence отличается — побеждает больший.
    - Если равно — побеждает существующий (стабильность).
    - Evidence объединяется (уникальные по source_url).
    """
    if existing is None:
        return deepcopy(incoming) if incoming else None
    if incoming is None:
        return existing

    existing_conf = existing.get("confidence", 0.0)
    incoming_conf = incoming.get("confidence", 0.0)

    # Объединяем evidence
    existing_evidence = existing.get("evidence", []) or []
    incoming_evidence = incoming.get("evidence", []) or []
    seen_urls = {e.get("source_url") for e in existing_evidence if e.get("source_url")}
    merged_evidence = list(existing_evidence)
    for e in incoming_evidence:
        if e.get("source_url") and e["source_url"] in seen_urls:
            continue
        merged_evidence.append(e)

    if incoming_conf > existing_conf:
        base = deepcopy(incoming)
    else:
        base = deepcopy(existing)
    base["evidence"] = merged_evidence
    return base


def _merge_list_of_strings(a: list[str] | None, b: list[str] | None) -> list[str]:
    """Объединяет списки строк, сохраняя порядок, убирая дубликаты."""
    result: list[str] = []
    seen: set[str] = set()
    for item in (a or []) + (b or []):
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_list_of_facts(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    """Объединяет списки fact-объектов (например, signals).

    Дедуп по (type, source_url).
    """
    result: list[dict] = []
    seen: set[tuple] = set()
    for item in (a or []) + (b or []):
        key = (item.get("type"), item.get("source_url"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def merge_company_payload(existing: dict, incoming: dict) -> dict:
    """Сливает два payload'а компании по правилам из docs/contracts.md."""
    result = deepcopy(existing)

    for field in ("name", "legal_name", "domain", "website", "industry", "sub_industry"):
        result[field] = _merge_fact(result.get(field), incoming.get(field))

    # size_estimate — вложенный объект с fact'ами
    existing_size = result.get("size_estimate", {}) or {}
    incoming_size = incoming.get("size_estimate", {}) or {}
    result["size_estimate"] = {
        "employee_count": _merge_fact(existing_size.get("employee_count"), incoming_size.get("employee_count")),
        "employee_range": incoming_size.get("employee_range") if incoming_size.get("employee_range") != "unknown" else existing_size.get("employee_range", "unknown"),
        "revenue_estimate": _merge_fact(existing_size.get("revenue_estimate"), incoming_size.get("revenue_estimate")),
        "revenue_currency": existing_size.get("revenue_currency") or incoming_size.get("revenue_currency"),
    }

    # locations — по is_hq + country/city
    result["locations"] = _merge_locations(result.get("locations"), incoming.get("locations"))

    # registry_ids — просто merge dict
    result["registry_ids"] = {**(result.get("registry_ids") or {}), **(incoming.get("registry_ids") or {})}

    # social_profiles — merge dict
    result["social_profiles"] = {**(result.get("social_profiles") or {}), **(incoming.get("social_profiles") or {})}

    # tech_stack — объединяем fact'ы по value
    result["tech_stack"] = _merge_tech_stack(result.get("tech_stack"), incoming.get("tech_stack"))

    # signals — объединяем
    result["signals"] = _merge_list_of_facts(result.get("signals"), incoming.get("signals"))

    # match — побеждает с большим score
    existing_match = result.get("match") or {}
    incoming_match = incoming.get("match") or {}
    if (incoming_match.get("score") or 0) > (existing_match.get("score") or 0):
        result["match"] = incoming_match
    else:
        result["match"] = existing_match

    # tags — объединяем
    result["tags"] = _merge_list_of_strings(result.get("tags"), incoming.get("tags"))

    # outreach_history — аккумулируем
    eh = result.get("outreach_history") or {}
    ih = incoming.get("outreach_history") or {}
    result["outreach_history"] = {
        "total_contacts": (eh.get("total_contacts") or 0) + (ih.get("total_contacts") or 0),
        "total_messages": (eh.get("total_messages") or 0) + (ih.get("total_messages") or 0),
        "last_contacted_at": _max_datetime(eh.get("last_contacted_at"), ih.get("last_contacted_at")),
    }

    # notes — конкатенируем с разделителем, если разные
    en = result.get("notes") or ""
    inc = incoming.get("notes") or ""
    if en and inc and en != inc:
        result["notes"] = f"{en}\n---\n{inc}"
    else:
        result["notes"] = en or inc

    return result


def _merge_locations(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    """Объединяет locations. Дедуп по (country, city, address)."""
    result: list[dict] = []
    seen: set[tuple] = set()
    for loc in (a or []) + (b or []):
        key = (
            (loc.get("country") or {}).get("value"),
            (loc.get("city") or {}).get("value"),
            (loc.get("address") or {}).get("value"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(loc)
    return result


def _merge_tech_stack(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    """Объединяет tech_stack по value, сливая evidence."""
    by_value: dict[str, dict] = {}
    for item in (a or []) + (b or []):
        value = item.get("value")
        if not value:
            continue
        if value not in by_value:
            by_value[value] = deepcopy(item)
        else:
            by_value[value]["confidence"] = max(
                by_value[value].get("confidence", 0.0),
                item.get("confidence", 0.0),
            )
            existing_ev = by_value[value].get("evidence", []) or []
            seen_urls = {e.get("source_url") for e in existing_ev if e.get("source_url")}
            for e in item.get("evidence", []) or []:
                if e.get("source_url") and e["source_url"] in seen_urls:
                    continue
                existing_ev.append(e)
            by_value[value]["evidence"] = existing_ev
    return list(by_value.values())


def _max_datetime(a: str | None, b: str | None) -> str | None:
    """Возвращает максимальную дату из двух ISO-строк."""
    if not a:
        return b
    if not b:
        return a
    return max(a, b)


def merge_contact_payload(existing: dict, incoming: dict) -> dict:
    """Сливает два payload'а контакта."""
    result = deepcopy(existing)

    for field in ("full_name", "first_name", "last_name", "patronymic", "position"):
        result[field] = _merge_fact(result.get(field), incoming.get(field))

    # role_category, seniority — enum'ы, побеждает не-unknown
    for field in ("role_category", "seniority"):
        ev = result.get(field)
        iv = incoming.get(field)
        if ev in (None, "unknown") and iv not in (None, "unknown"):
            result[field] = iv
        else:
            result[field] = ev or iv or "unknown"

    # emails — merge по value
    result["emails"] = _merge_emails(result.get("emails"), incoming.get("emails"))
    # phones
    result["phones"] = _merge_phones(result.get("phones"), incoming.get("phones"))
    # messengers — по (channel, handle)
    result["messengers"] = _merge_messengers(result.get("messengers"), incoming.get("messengers"))

    # social_profiles, location — merge dict / fact
    result["social_profiles"] = {**(result.get("social_profiles") or {}), **(incoming.get("social_profiles") or {})}

    existing_loc = result.get("location") or {}
    incoming_loc = incoming.get("location") or {}
    result["location"] = {
        "country": _merge_fact(existing_loc.get("country"), incoming_loc.get("country")),
        "city": _merge_fact(existing_loc.get("city"), incoming_loc.get("city")),
        "timezone": existing_loc.get("timezone") or incoming_loc.get("timezone"),
    }

    result["language_preference"] = result.get("language_preference") or incoming.get("language_preference")

    # match — по role_match_score
    em = result.get("match") or {}
    im = incoming.get("match") or {}
    if (im.get("role_match_score") or 0) > (em.get("role_match_score") or 0):
        result["match"] = im
    else:
        result["match"] = em

    # consent — самый строгий wins (denied > granted > unknown)
    result["consent"] = _merge_consent(result.get("consent"), incoming.get("consent"))

    # outreach_history — аккумулируем
    eh = result.get("outreach_history") or {}
    ih = incoming.get("outreach_history") or {}
    result["outreach_history"] = {
        "total_messages": (eh.get("total_messages") or 0) + (ih.get("total_messages") or 0),
        "last_contacted_at": _max_datetime(eh.get("last_contacted_at"), ih.get("last_contacted_at")),
        "last_reply_at": _max_datetime(eh.get("last_reply_at"), ih.get("last_reply_at")),
        "replied_positive": bool(eh.get("replied_positive") or ih.get("replied_positive")),
    }

    result["tags"] = _merge_list_of_strings(result.get("tags"), incoming.get("tags"))
    result["notes"] = _merge_notes(result.get("notes"), incoming.get("notes"))
    return result


def _merge_emails(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    by_value: dict[str, dict] = {}
    for e in (a or []) + (b or []):
        v = e.get("value")
        if not v:
            continue
        if v not in by_value:
            by_value[v] = deepcopy(e)
        else:
            by_value[v]["confidence"] = max(by_value[v].get("confidence", 0.0), e.get("confidence", 0.0))
            by_value[v]["is_verified"] = bool(by_value[v].get("is_verified") or e.get("is_verified"))
            by_value[v]["type"] = by_value[v].get("type") if by_value[v].get("type") != "unknown" else e.get("type", "unknown")
    # Пересчитываем primary: выбираем с максимальной confidence
    result = list(by_value.values())
    if result:
        best = max(result, key=lambda x: x.get("confidence", 0.0))
        for e in result:
            e["is_primary"] = (e["value"] == best["value"])
    return result


def _merge_phones(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    by_value: dict[str, dict] = {}
    for p in (a or []) + (b or []):
        v = p.get("value")
        if not v:
            continue
        if v not in by_value:
            by_value[v] = deepcopy(p)
        else:
            by_value[v]["confidence"] = max(by_value[v].get("confidence", 0.0), p.get("confidence", 0.0))
            by_value[v]["is_whatsapp"] = bool(by_value[v].get("is_whatsapp") or p.get("is_whatsapp"))
            by_value[v]["is_telegram"] = bool(by_value[v].get("is_telegram") or p.get("is_telegram"))
    result = list(by_value.values())
    if result:
        best = max(result, key=lambda x: x.get("confidence", 0.0))
        for p in result:
            p["is_primary"] = (p["value"] == best["value"])
    return result


def _merge_messengers(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    by_key: dict[tuple, dict] = {}
    for m in (a or []) + (b or []):
        key = (m.get("channel"), m.get("handle"))
        if not all(key):
            continue
        if key not in by_key:
            by_key[key] = deepcopy(m)
        else:
            by_key[key]["confidence"] = max(by_key[key].get("confidence", 0.0), m.get("confidence", 0.0))
    return list(by_key.values())


def _merge_consent(a: dict | None, b: dict | None) -> dict:
    a = a or {}
    b = b or {}
    rank = {"denied": 3, "granted": 2, "not_required": 1, "unknown": 0}
    result = deepcopy(a)
    for field in ("email_opt_in", "messenger_opt_in"):
        av = a.get(field, "unknown")
        bv = b.get(field, "unknown")
        result[field] = av if rank.get(av, 0) >= rank.get(bv, 0) else bv
    result["email_opt_in_source"] = a.get("email_opt_in_source") or b.get("email_opt_in_source")
    result["email_opt_in_at"] = a.get("email_opt_in_at") or b.get("email_opt_in_at")
    result["gdpr_lawful_basis"] = a.get("gdpr_lawful_basis") or b.get("gdpr_lawful_basis") or "unknown"
    result["notes"] = _merge_notes(a.get("notes"), b.get("notes"))
    return result


def _merge_notes(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    if a == b:
        return a
    return f"{a}\n---\n{b}"
```

**Важно:** merger работает только с payload'ами (dict). Он не трогает БД. Вызов из `service.py`, который читает существующую запись, вызывает `merge_company_payload(existing.payload, incoming_payload)`, обновляет поля и сохраняет.

### Тесты

`tests/test_merger.py`:

```python
import pytest
from contact_store.merger import (
    _merge_fact,
    _merge_list_of_strings,
    merge_company_payload,
    merge_contact_payload,
)


def test_merge_fact_incoming_wins_with_higher_confidence():
    existing = {"value": "old", "confidence": 0.5, "evidence": []}
    incoming = {"value": "new", "confidence": 0.9, "evidence": []}
    result = _merge_fact(existing, incoming)
    assert result["value"] == "new"


def test_merge_fact_existing_wins_on_tie():
    existing = {"value": "old", "confidence": 0.5, "evidence": []}
    incoming = {"value": "new", "confidence": 0.5, "evidence": []}
    result = _merge_fact(existing, incoming)
    assert result["value"] == "old"


def test_merge_fact_combines_evidence():
    existing = {"value": "x", "confidence": 0.5, "evidence": [{"source_url": "a"}]}
    incoming = {"value": "x", "confidence": 0.5, "evidence": [{"source_url": "b"}]}
    result = _merge_fact(existing, incoming)
    urls = {e["source_url"] for e in result["evidence"]}
    assert urls == {"a", "b"}


def test_merge_company_payload_basic():
    existing = {
        "name": {"value": "X", "confidence": 0.8, "evidence": []},
        "tags": ["a", "b"],
        "signals": [],
    }
    incoming = {
        "name": {"value": "X Corp", "confidence": 0.9, "evidence": []},
        "tags": ["b", "c"],
        "signals": [{"type": "news", "source_url": "u1", "summary": "..."}],
    }
    result = merge_company_payload(existing, incoming)
    assert result["name"]["value"] == "X Corp"
    assert result["tags"] == ["a", "b", "c"]
    assert len(result["signals"]) == 1


def test_merge_company_payload_no_mutation():
    existing = {"name": {"value": "X", "confidence": 0.5, "evidence": []}, "tags": []}
    incoming = {"name": {"value": "Y", "confidence": 0.9, "evidence": []}, "tags": ["a"]}
    _ = merge_company_payload(existing, incoming)
    # existing не должен измениться
    assert existing["name"]["value"] == "X"
    assert existing["tags"] == []


def test_merge_contact_payload_emails():
    existing = {
        "emails": [{"value": "a@x.com", "confidence": 0.9, "is_primary": True, "type": "work"}],
        "full_name": {"value": "Иван", "confidence": 0.7, "evidence": []},
    }
    incoming = {
        "emails": [
            {"value": "a@x.com", "confidence": 0.5, "is_primary": False, "type": "unknown"},
            {"value": "b@x.com", "confidence": 0.8, "is_primary": False, "type": "work"},
        ],
        "full_name": {"value": "Иван Петров", "confidence": 0.9, "evidence": []},
    }
    result = merge_contact_payload(existing, incoming)
    # a@x.com должен быть primary (0.9 > 0.8)
    primary = next(e for e in result["emails"] if e["is_primary"])
    assert primary["value"] == "a@x.com"
    assert len(result["emails"]) == 2
```

## Acceptance criteria

```bash
uv run pytest services/contact-store/tests/test_merger.py -v --cov=contact_store.merger --cov-report=term-missing
# Ожидание: coverage >= 90%

uv run mypy services/contact-store
uv run ruff check services/contact-store
```

## Подсказки

- **`deepcopy` обязателен.** Иначе merge мутирует исходные dict'ы, и это приведёт к невоспроизводимым багам.
- **Evidence-дедуп по `source_url`.** Если у двух evidence одинаковый URL — оставляем первый.
- **Primary email/phone** пересчитывается после merge: побеждает с максимальной confidence.
- **`consent`** — самый строгий wins. Если в одном месте `denied`, а в другом `unknown` — итог `denied`.
- **Notes** объединяются через `\n---\n`. Если одинаковые — не дублируем.

## Анти-паттерны

- ❌ Не мутировать исходные dict'ы.
- ❌ Не терять evidence при merge.
- ❌ Не позволять `unknown` перезаписывать известные значения.
- ❌ Не забывать про primary после merge emails/phones.
- ❌ Не конкатенировать одинаковые notes.

---

# Задача 2A.4 — StopList

**Файл:** `docs/tasks/sprint-2a/2a.4-stoplist.md`

## Цель

Реализовать проверку stop-листа перед созданием/обновлением контакта. Глобальные записи (shared между тенантами) + тенант-скоупные.

## Зависимости

2A.1.

## Что создать

```
services/contact-store/src/contact_store/
└── stoplist.py

services/contact-store/tests/
└── test_stoplist.py
```

## Детали реализации

### `stoplist.py`

```python
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from contact_store.models import StopListEntry


class StopList:
    """Проверка и управление stop-листом."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def is_blocked(
        self,
        *,
        tenant_id: UUID,
        email: str | None = None,
        phone: str | None = None,
        domain: str | None = None,
    ) -> tuple[bool, str | None]:
        """Проверяет, заблокирован ли контакт/домен.

        Возвращает (is_blocked, reason).
        """
        checks: list[tuple[str, str]] = []
        if email:
            checks.append(("email", email))
        if phone:
            checks.append(("phone", phone))
        if domain:
            checks.append(("domain", domain))

        if not checks:
            return False, None

        # RLS: видим global (tenant_id IS NULL) + свои
        for kind, value in checks:
            stmt = select(StopListEntry).where(
                StopListEntry.kind == kind,
                StopListEntry.value == value,
            )
            entry = (await self._s.execute(stmt)).scalar_one_or_none()
            if entry is not None:
                return True, entry.reason
        return False, None

    async def add(
        self,
        *,
        tenant_id: UUID,
        kind: str,
        value: str,
        reason: str,
        note: str | None = None,
        created_by: str = "system",
        scope: str = "tenant",
    ) -> StopListEntry:
        """Добавляет запись. scope='global' — только для системной роли."""
        entry = StopListEntry(
            tenant_id=tenant_id if scope == "tenant" else None,
            scope=scope,
            kind=kind,
            value=value,
            reason=reason,
            note=note,
            created_by=created_by,
        )
        self._s.add(entry)
        await self._s.flush()
        return entry

    async def remove(self, entry_id: UUID) -> bool:
        entry = await self._s.get(StopListEntry, entry_id)
        if entry is None:
            return False
        await self._s.delete(entry)
        return True

    async def list(
        self,
        *,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StopListEntry]:
        stmt = select(StopListEntry)
        if kind:
            stmt = stmt.where(StopListEntry.kind == kind)
        stmt = stmt.order_by(StopListEntry.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
```

**Важно:** `is_blocked` использует RLS для фильтрации. Но RLS работает только если `app.tenant_id` установлен. В `service.py` через `get_service` это уже делается. Если проверяем для другого тенанта — нужно временно переключить контекст. Не делаем этого: `is_blocked` всегда для текущего тенанта.

**Важно про `add`:** создать глобальную запись может только системная роль (не через API тенанта). В 2A API даёт только tenant-скоуп. Global создаётся либо в миграции, либо админским эндпоинтом (позже).

### `api/routes_stoplist.py`

```python
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from common.context import get_tenant_id
from common.errors import ValidationError
from contact_store.api.deps import get_stoplist
from contact_store.schemas import StopListEntryCreate, StopListEntryRead
from contact_store.stoplist import StopList


router = APIRouter(prefix="/stoplist", tags=["stoplist"])


@router.post("", response_model=StopListEntryRead, status_code=status.HTTP_201_CREATED)
async def add_entry(
    data: StopListEntryCreate,
    request: Request,
    sl: StopList = Depends(get_stoplist),
) -> StopListEntryRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    entry = await sl.add(
        tenant_id=tenant_id,
        kind=data.kind,
        value=data.value,
        reason=data.reason,
        note=data.note,
        created_by=request.headers.get("X-User-Id", "anonymous"),
    )
    return StopListEntryRead.model_validate(entry, from_attributes=True)


@router.get("", response_model=list[StopListEntryRead])
async def list_entries(
    kind: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sl: StopList = Depends(get_stoplist),
) -> list[StopListEntryRead]:
    entries = await sl.list(kind=kind, limit=limit, offset=offset)
    return [StopListEntryRead.model_validate(e, from_attributes=True) for e in entries]


@router.delete("/{entry_id}", status_code=204)
async def remove_entry(
    entry_id: UUID,
    sl: StopList = Depends(get_stoplist),
) -> None:
    await sl.remove(entry_id)
```

### `schemas.py` (дополнить)

```python
class StopListEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(email|phone|domain)$")
    value: str = Field(min_length=1, max_length=512)
    reason: str = Field(pattern="^(unsubscribed|bounced_hard|complained|manual|disqualified)$")
    note: str | None = None


class StopListEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    tenant_id: UUID | None
    scope: str
    kind: str
    value: str
    reason: str
    note: str | None
    created_by: str
    created_at: datetime
```

### Тесты

`tests/test_stoplist.py`:

```python
import pytest
from uuid import uuid4

from contact_store.stoplist import StopList


@pytest.mark.asyncio
async def test_add_and_check_email(session, tenant_id):
    sl = StopList(session)
    await sl.add(tenant_id=tenant_id, kind="email", value="x@y.com", reason="unsubscribed")
    blocked, reason = await sl.is_blocked(tenant_id=tenant_id, email="x@y.com")
    assert blocked
    assert reason == "unsubscribed"


@pytest.mark.asyncio
async def test_not_blocked(session, tenant_id):
    sl = StopList(session)
    blocked, _ = await sl.is_blocked(tenant_id=tenant_id, email="unknown@y.com")
    assert not blocked


@pytest.mark.asyncio
async def test_global_entry_visible_to_all(session, tenant_id):
    sl = StopList(session)
    await sl.add(tenant_id=tenant_id, kind="email", value="global@y.com", reason="complained", scope="global")
    # Другой тенант тоже видит
    other = uuid4()
    blocked, _ = await sl.is_blocked(tenant_id=other, email="global@y.com")
    assert blocked


@pytest.mark.asyncio
async def test_tenant_entry_not_visible_to_others(session, tenant_id):
    sl = StopList(session)
    await sl.add(tenant_id=tenant_id, kind="email", value="private@y.com", reason="unsubscribed", scope="tenant")
    other = uuid4()
    blocked, _ = await sl.is_blocked(tenant_id=other, email="private@y.com")
    assert not blocked
```

## Acceptance criteria

```bash
uv run pytest services/contact-store/tests/test_stoplist.py -v
# Ожидание: все passed

# E2E через API
curl -X POST https://contact-store.dev.aitler.ru/stoplist \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: sl-1" \
  -d '{"kind":"email","value":"blocked@example.com","reason":"unsubscribed"}'

curl -H "X-Tenant-ID: $TENANT" https://contact-store.dev.aitler.ru/stoplist | jq .
# Ожидание: запись есть
```

## Подсказки

- **Глобальные записи** — `tenant_id=NULL`, `scope='global'`. RLS-политика позволяет их читать всем.
- **Создание глобальной записи** через API — запрещено (RLS `WITH CHECK` не пропустит). Только миграция или админский эндпоинт с отдельной ролью.
- **Проверка stop-list** — обязательна перед upsert контакта. Если email в stop-list — не создаём контакт, возвращаем `blocked`.

## Анти-паттерны

- ❌ Не позволять тенанту создавать глобальные записи через API.
- ❌ Не забыть RLS-политику для stoplist — она отличается от остальных.
- ❌ Не проверять stop-list только по email — проверяем и phone, и domain.

---

# Задача 2A.5 — Компании: CRUD + upsert + bulk

**Файл:** `docs/tasks/sprint-2a/2a.5-companies-api.md`

## Цель

Реализовать API для компаний: создание (upsert), получение, список, обновление, bulk upsert. Внутри — дедуп через fingerprint, merge через merger, публикация событий.

## Зависимости

2A.1–2A.4.

## Что создать

- `services/contact-store/src/contact_store/repository.py` — `CompanyRepository`.
- `services/contact-store/src/contact_store/service.py` — `CompanyService`.
- `services/contact-store/src/contact_store/schemas.py` — доп. схемы.
- `services/contact-store/src/contact_store/events.py` — события по компаниям.
- `services/contact-store/src/contact_store/api/routes_companies.py`.
- `services/contact-store/src/contact_store/api/deps.py`.
- Тесты.

### `schemas.py` — доп. схемы

```python
class CompanyUpsert(BaseModel):
    """Вход для upsert компании."""
    model_config = ConfigDict(extra="forbid")

    payload: dict  # валидируется против contracts.Company
    status: str = "candidate"


class CompanyRead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    tenant_id: UUID
    fingerprint: str
    status: str
    payload: dict
    contacts_count: int
    last_contacted_at: datetime | None
    schema_version: str
    created_at: datetime
    updated_at: datetime


class CompanyUpsertResult(BaseModel):
    """Результат upsert — что произошло."""
    company: CompanyRead
    action: str  # "created" | "updated" | "merged"


class CompanyBulkUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CompanyUpsert] = Field(min_length=1, max_length=500)


class CompanyBulkResult(BaseModel):
    created: int
    updated: int
    merged: int
    results: list[CompanyUpsertResult]
    errors: list[dict]  # [{index, error}]
```

### `repository.py`

```python
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contact_store.models import Company, Contact


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, company_id: UUID) -> Company | None:
        return await self._s.get(Company, company_id)

    async def get_by_fingerprint(self, tenant_id: UUID, fingerprint: str) -> Company | None:
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            Company.fingerprint == fingerprint,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_by_domain(self, tenant_id: UUID, domain: str) -> Company | None:
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            Company.domain_normalized == domain,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_by_inn(self, tenant_id: UUID, inn: str) -> Company | None:
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            Company.inn == inn,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Company]:
        stmt = select(Company).where(Company.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Company.status == status)
        stmt = stmt.order_by(Company.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def add(self, company: Company) -> Company:
        self._s.add(company)
        await self._s.flush()
        return company

    async def update_contacts_count(self, company_id: UUID) -> None:
        stmt = select(func.count(Contact.id)).where(Contact.company_id == company_id)
        count = (await self._s.execute(stmt)).scalar_one()
        company = await self._s.get(Company, company_id)
        if company is not None:
            company.contacts_count = count
```

### `service.py` — `CompanyService`

```python
from datetime import datetime, timezone
from uuid import UUID

import structlog

from common.errors import ValidationError
from contact_store.fingerprint import company_fingerprint
from contact_store.merger import merge_company_payload
from contact_store.models import Company
from contact_store.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_inn,
    normalize_ogrn,
)
from contact_store.repository import CompanyRepository
from nats_client.publisher import Publisher
from contact_store import events


logger = structlog.get_logger()


class CompanyService:
    def __init__(
        self,
        repo: CompanyRepository,
        publisher: Publisher,
    ) -> None:
        self._repo = repo
        self._publisher = publisher

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        payload: dict,
        status: str = "candidate",
        trace_id: str = "",
    ) -> tuple[Company, str]:
        """Upsert компании. Возвращает (company, action).

        action: "created" | "updated" | "merged".
        """
        normalized = self._normalize_payload(payload)
        fingerprint = company_fingerprint(
            name_normalized=normalized["name_normalized"],
            domain_normalized=normalized["domain_normalized"],
            inn=normalized["inn"],
        )

        existing = await self._repo.get_by_fingerprint(tenant_id, fingerprint)
        if existing is None:
            # Попробуем найти по домену или ИНН — если fingerprint не совпал,
            # но домен/ИНН те же, значит что-то изменилось (например, название)
            if normalized["inn"]:
                existing = await self._repo.get_by_inn(tenant_id, normalized["inn"])
            if existing is None and normalized["domain_normalized"]:
                existing = await self._repo.get_by_domain(tenant_id, normalized["domain_normalized"])

        if existing is None:
            company = Company(
                tenant_id=tenant_id,
                fingerprint=fingerprint,
                status=status,
                name_normalized=normalized["name_normalized"],
                domain_normalized=normalized["domain_normalized"],
                inn=normalized["inn"],
                ogrn=normalized["ogrn"],
                payload=payload,
            )
            await self._repo.add(company)
            await events.emit_company_created(self._publisher, company, trace_id=trace_id)
            return company, "created"

        # Merge
        merged_payload = merge_company_payload(existing.payload, payload)
        action = "merged" if merged_payload != existing.payload else "updated"

        existing.payload = merged_payload
        existing.name_normalized = normalized["name_normalized"]
        existing.domain_normalized = normalized["domain_normalized"] or existing.domain_normalized
        existing.inn = normalized["inn"] or existing.inn
        existing.ogrn = normalized["ogrn"] or existing.ogrn
        if status and status != "candidate":
            existing.status = status
        await self._repo._s.flush()

        if action == "merged":
            await events.emit_company_merged(self._publisher, existing, trace_id=trace_id)
        else:
            await events.emit_company_updated(self._publisher, existing, trace_id=trace_id)
        return existing, action

    async def bulk_upsert(
        self,
        *,
        tenant_id: UUID,
        items: list[dict],
        trace_id: str = "",
    ) -> dict:
        results = []
        errors = []
        created = updated = merged = 0
        for i, item in enumerate(items):
            try:
                company, action = await self.upsert(
                    tenant_id=tenant_id,
                    payload=item["payload"],
                    status=item.get("status", "candidate"),
                    trace_id=trace_id,
                )
                results.append({"company": company, "action": action})
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1
                else:
                    merged += 1
            except Exception as e:
                logger.exception("bulk_upsert_item_failed", index=i)
                errors.append({"index": i, "error": str(e)})
        return {
            "created": created,
            "updated": updated,
            "merged": merged,
            "results": results,
            "errors": errors,
        }

    def _normalize_payload(self, payload: dict) -> dict:
        """Извлекает нормализованные поля из payload."""
        name_fact = payload.get("name") or {}
        name_value = name_fact.get("value") if isinstance(name_fact, dict) else None
        if not name_value:
            raise ValidationError("Company payload must have name.value")

        domain_fact = payload.get("domain") or {}
        domain_value = domain_fact.get("value") if isinstance(domain_fact, dict) else None

        registry = payload.get("registry_ids") or {}
        inn_raw = registry.get("ru_inn")
        ogrn_raw = registry.get("ru_ogrn")

        return {
            "name_normalized": normalize_company_name(name_value),
            "domain_normalized": normalize_domain(domain_value),
            "inn": normalize_inn(inn_raw),
            "ogrn": normalize_ogrn(ogrn_raw),
        }

    async def get(self, company_id: UUID) -> Company:
        from common.errors import NotFoundError
        company = await self._repo.get(company_id)
        if company is None:
            raise NotFoundError(f"Company {company_id} not found")
        return company

    async def list(self, *, tenant_id: UUID, status: str | None, limit: int, offset: int) -> list[Company]:
        return await self._repo.list(tenant_id=tenant_id, status=status, limit=limit, offset=offset)
```

### `events.py`

```python
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from contact_store.models import Company


async def emit_company_created(publisher: Publisher, company: Company, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.COMPANY_CREATED,
        tenant_id=company.tenant_id,
        payload={"company": {"id": str(company.id), "fingerprint": company.fingerprint, "status": company.status}},
        trace_id=trace_id,
        correlation_id=company.id,
    )


async def emit_company_updated(publisher: Publisher, company: Company, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.COMPANY_UPDATED,
        tenant_id=company.tenant_id,
        payload={"company": {"id": str(company.id), "fingerprint": company.fingerprint}},
        trace_id=trace_id,
        correlation_id=company.id,
    )


async def emit_company_merged(publisher: Publisher, company: Company, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.COMPANY_MERGED,
        tenant_id=company.tenant_id,
        payload={"company": {"id": str(company.id), "fingerprint": company.fingerprint}},
        trace_id=trace_id,
        correlation_id=company.id,
    )
```

**Важно:** добавить `COMPANY_CREATED`, `COMPANY_UPDATED`, `COMPANY_MERGED` в `libs/nats-client/src/nats_client/subjects.py`. Это расширение — minor.

Также добавить `COMPANY_*` в `_SUBJECT_TO_STREAM` — маппинг на стрим `BRIEFS` (или создать отдельный `CONTACTS`? Лучше отдельный — данные объёмные). **Решение:** создать стрим `CONTACTS` в `streams.py`:

```python
StreamConfig(
    name="CONTACTS",
    subjects=["company.>", "contact.>"],
    max_age_seconds=365 * 24 * 3600,
    max_bytes=5 * 1024 * 1024 * 1024,
    storage="file",
    retention="limits",
),
```

И маппинг:
```python
"company": "CONTACTS",
"contact": "CONTACTS",
```

### `api/routes_companies.py`

```python
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from contact_store.api.deps import get_company_service
from contact_store.schemas import (
    CompanyBulkResult,
    CompanyBulkUpsert,
    CompanyRead,
    CompanyUpsert,
    CompanyUpsertResult,
)
from contact_store.service import CompanyService


router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyUpsertResult, status_code=status.HTTP_201_CREATED)
async def upsert_company(
    data: CompanyUpsert,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyUpsertResult:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    company, action = await svc.upsert(
        tenant_id=tenant_id,
        payload=data.payload,
        status=data.status,
        trace_id=get_trace_id() or "",
    )
    return CompanyUpsertResult(
        company=CompanyRead.model_validate(company, from_attributes=True),
        action=action,
    )


@router.post("/bulk", response_model=CompanyBulkResult)
async def bulk_upsert(
    data: CompanyBulkUpsert,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyBulkResult:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    result = await svc.bulk_upsert(
        tenant_id=tenant_id,
        items=[item.model_dump() for item in data.items],
        trace_id=get_trace_id() or "",
    )
    return CompanyBulkResult(
        created=result["created"],
        updated=result["updated"],
        merged=result["merged"],
        results=[
            CompanyUpsertResult(
                company=CompanyRead.model_validate(r["company"], from_attributes=True),
                action=r["action"],
            )
            for r in result["results"]
        ],
        errors=result["errors"],
    )


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: UUID,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = await svc.get(company_id)
    return CompanyRead.model_validate(company, from_attributes=True)


@router.get("", response_model=list[CompanyRead])
async def list_companies(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: CompanyService = Depends(get_company_service),
) -> list[CompanyRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    companies = await svc.list(tenant_id=tenant_id, status=status_filter, limit=limit, offset=offset)
    return [CompanyRead.model_validate(c, from_attributes=True) for c in companies]
```

### `api/deps.py`

```python
from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from contact_store.repository import CompanyRepository
from contact_store.service import CompanyService


async def get_company_service(request: Request) -> AsyncIterator[CompanyService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session:
        async with session.begin():
            if tenant_id is not None:
                await set_tenant_context(session, tenant_id)
            yield CompanyService(
                repo=CompanyRepository(session),
                publisher=request.app.state.publisher,
            )
```

### Тесты

`tests/test_companies_api.py`:

```python
import pytest
from httpx import AsyncClient


def _company_payload(name: str = "Test Corp", domain: str | None = None) -> dict:
    return {
        "name": {"value": name, "confidence": 1.0, "evidence": []},
        "domain": {"value": domain, "confidence": 1.0, "evidence": []} if domain else None,
        "industry": {"value": "IT", "confidence": 0.8, "evidence": []},
    }


@pytest.mark.asyncio
async def test_upsert_company_creates(client: AsyncClient, headers):
    resp = await client.post(
        "/companies",
        json={"payload": _company_payload("Test", "test.com")},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["action"] == "created"


@pytest.mark.asyncio
async def test_upsert_company_merges(client: AsyncClient, headers):
    # Создаём
    await client.post(
        "/companies",
        json={"payload": _company_payload("Test", "test.com")},
        headers={**headers, "Idempotency-Key": "c1"},
    )
    # Второй раз с тем же доменом — merge
    resp = await client.post(
        "/companies",
        json={"payload": _company_payload("Test Corp", "test.com")},
        headers={**headers, "Idempotency-Key": "c2"},
    )
    assert resp.status_code == 201
    assert resp.json()["action"] in ("merged", "updated")


@pytest.mark.asyncio
async def test_bulk_upsert(client: AsyncClient, headers):
    items = [
        {"payload": _company_payload(f"Company {i}", f"company{i}.com")}
        for i in range(5)
    ]
    resp = await client.post(
        "/companies/bulk",
        json={"items": items},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 5
    assert len(data["results"]) == 5
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_rls_isolation(client: AsyncClient):
    h_a = {"X-Tenant-ID": "00000000-0000-0000-0000-00000000000a", "Idempotency-Key": "a1"}
    h_b = {"X-Tenant-ID": "00000000-0000-0000-0000-00000000000b"}

    create = await client.post("/companies", json={"payload": _company_payload("A", "a.com")}, headers=h_a)
    company_id = create.json()["company"]["id"]

    resp = await client.get(f"/companies/{company_id}", headers=h_b)
    assert resp.status_code == 404
```

## Acceptance criteria

```bash
uv run pytest services/contact-store/tests/test_companies_api.py -v
# Ожидание: все passed

# E2E
curl -X POST https://contact-store.dev.aitler.ru/companies \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: c1" \
  -d '{"payload":{"name":{"value":"ООО Ромашка","confidence":1.0,"evidence":[]},"domain":{"value":"romashka.ru","confidence":1.0,"evidence":[]}}}' | jq .
# Ожидание: action: "created"

# Повторно с тем же доменом
curl -X POST https://contact-store.dev.aitler.ru/companies \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: c2" \
  -d '{"payload":{"name":{"value":"Ромашка","confidence":1.0,"evidence":[]},"domain":{"value":"https://www.romashka.ru","confidence":1.0,"evidence":[]}}}' | jq .action
# Ожидание: "merged"

# Bulk
curl -X POST https://contact-store.dev.aitler.ru/companies/bulk \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: bulk-1" \
  -d '{"items":[{"payload":{"name":{"value":"A","confidence":1.0,"evidence":[]}}},{"payload":{"name":{"value":"B","confidence":1.0,"evidence":[]}}}]}' | jq .
# Ожидание: created: 2
```

## Подсказки

- **Upsert сначала по fingerprint, потом по домену/ИНН.** Если fingerprint не совпал (например, изменилось название, но домен тот же) — ищем по домену и мержим. Это позволяет избежать дубликатов при небольших изменениях в данных.
- **Merge — не всегда «merged».** Если payload не изменился — это «updated». Различаем, чтобы не спамить событиями.
- **Bulk — синхронный.** До 500 записей. Если больше — разбивать на батчи на клиенте.
- **`X-Tenant-ID` обязателен** на всех эндпоинтах.

## Анти-паттерны

- ❌ Не создавать дубликат при том же домене, но другом названии.
- ❌ Не делать `insert` без проверки fingerprint.
- ❌ Не забывать `Idempotency-Key` в тестах — иначе middleware не сработает.
- ❌ Не публиковать событие до flush.

---

# Задача 2A.6 — Контакты: CRUD + upsert + bulk + проверка stop-list

**Файл:** `docs/tasks/sprint-2a/2a.6-contacts-api.md`

## Цель

Аналогично компаниям, но для контактов. Плюс обязательная проверка stop-list перед созданием. Плюс работа с `ContactEmail`/`ContactPhone` (вынесенные таблицы).

## Зависимости

2A.1–2A.5.

## Что создать

- `ContactRepository` в `repository.py`.
- `ContactService` в `service.py`.
- События по контактам в `events.py`.
- `api/routes_contacts.py`.
- `api/deps.py` — `get_contact_service`.
- Схемы.
- Тесты.

## Детали

### `ContactRepository`

```python
class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, contact_id: UUID) -> Contact | None:
        return await self._s.get(Contact, contact_id)

    async def get_by_fingerprint(self, tenant_id: UUID, fingerprint: str) -> Contact | None:
        stmt = select(Contact).where(
            Contact.tenant_id == tenant_id,
            Contact.fingerprint == fingerprint,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, tenant_id: UUID, email: str) -> Contact | None:
        stmt = (
            select(Contact)
            .join(ContactEmail, ContactEmail.contact_id == Contact.id)
            .where(ContactEmail.tenant_id == tenant_id, ContactEmail.value == email)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_by_phone(self, tenant_id: UUID, phone: str) -> Contact | None:
        stmt = (
            select(Contact)
            .join(ContactPhone, ContactPhone.contact_id == Contact.id)
            .where(ContactPhone.tenant_id == tenant_id, ContactPhone.value == phone)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list_by_company(self, company_id: UUID, limit: int = 200) -> list[Contact]:
        stmt = select(Contact).where(Contact.company_id == company_id).limit(limit)
        return list((await self._s.execute(stmt)).scalars().all())

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        company_id: UUID | None = None,
        role_category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        stmt = select(Contact).where(Contact.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Contact.status == status)
        if company_id:
            stmt = stmt.where(Contact.company_id == company_id)
        if role_category:
            stmt = stmt.where(Contact.role_category == role_category)
        stmt = stmt.order_by(Contact.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def add(self, contact: Contact) -> Contact:
        self._s.add(contact)
        await self._s.flush()
        return contact
```

### `ContactService` — ключевая логика

```python
class ContactService:
    def __init__(
        self,
        repo: ContactRepository,
        company_repo: CompanyRepository,
        stoplist: StopList,
        publisher: Publisher,
    ) -> None:
        ...

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        payload: dict,
        status: str = "candidate",
        trace_id: str = "",
    ) -> tuple[Contact | None, str]:
        """Upsert контакта.

        Возвращает:
        - (contact, action) при успехе. action: "created" | "updated" | "merged".
        - (None, "blocked:<reason>") если email/phone в stop-list.
        """
        normalized = self._normalize_payload(payload)

        # Stop-list проверка
        blocked, reason = await self._stoplist.is_blocked(
            tenant_id=tenant_id,
            email=normalized["primary_email"],
            phone=normalized["primary_phone"],
        )
        if blocked:
            logger.info("contact_blocked_by_stoplist", reason=reason, email=normalized["primary_email"])
            return None, f"blocked:{reason}"

        fingerprint = contact_fingerprint(
            email=normalized["primary_email"],
            phone=normalized["primary_phone"],
            full_name_normalized=normalized["full_name_normalized"],
            company_domain=normalized["company_domain"],
        )

        existing = await self._repo.get_by_fingerprint(tenant_id, fingerprint)
        if existing is None:
            # Пробуем по email/phone — если fingerprint не совпал, но email тот же
            if normalized["primary_email"]:
                existing = await self._repo.get_by_email(tenant_id, normalized["primary_email"])
            if existing is None and normalized["primary_phone"]:
                existing = await self._repo.get_by_phone(tenant_id, normalized["primary_phone"])

        if existing is None:
            contact = Contact(
                tenant_id=tenant_id,
                company_id=normalized["company_id"],
                fingerprint=fingerprint,
                status=status,
                full_name_normalized=normalized["full_name_normalized"],
                primary_email=normalized["primary_email"],
                primary_phone=normalized["primary_phone"],
                role_category=normalized["role_category"],
                seniority=normalized["seniority"],
                payload=payload,
            )
            await self._repo.add(contact)
            await self._sync_emails_phones(tenant_id, contact.id, payload)
            if normalized["company_id"]:
                await self._company_repo.update_contacts_count(normalized["company_id"])
            await events.emit_contact_created(self._publisher, contact, trace_id=trace_id)
            return contact, "created"

        # Merge
        merged_payload = merge_contact_payload(existing.payload, payload)
        action = "merged" if merged_payload != existing.payload else "updated"

        existing.payload = merged_payload
        existing.full_name_normalized = normalized["full_name_normalized"] or existing.full_name_normalized
        existing.primary_email = normalized["primary_email"] or existing.primary_email
        existing.primary_phone = normalized["primary_phone"] or existing.primary_phone
        existing.role_category = normalized["role_category"] if normalized["role_category"] != "unknown" else existing.role_category
        existing.seniority = normalized["seniority"] if normalized["seniority"] != "unknown" else existing.seniority
        if normalized["company_id"] and not existing.company_id:
            existing.company_id = normalized["company_id"]
        if status and status != "candidate":
            existing.status = status
        await self._repo._s.flush()

        await self._sync_emails_phones(tenant_id, existing.id, merged_payload)
        if existing.company_id:
            await self._company_repo.update_contacts_count(existing.company_id)

        if action == "merged":
            await events.emit_contact_merged(self._publisher, existing, trace_id=trace_id)
        else:
            await events.emit_contact_updated(self._publisher, existing, trace_id=trace_id)
        return existing, action

    async def update_status(
        self,
        contact_id: UUID,
        *,
        status: str,
        trace_id: str = "",
    ) -> Contact:
        contact = await self.get(contact_id)
        contact.status = status
        await self._repo._s.flush()
        if status == "unsubscribed":
            # Добавляем в stop-list
            if contact.primary_email:
                await self._stoplist.add(
                    tenant_id=contact.tenant_id,
                    kind="email",
                    value=contact.primary_email,
                    reason="unsubscribed",
                )
            await events.emit_contact_unsubscribed(self._publisher, contact, trace_id=trace_id)
        else:
            await events.emit_contact_updated(self._publisher, contact, trace_id=trace_id)
        return contact

    async def _sync_emails_phones(self, tenant_id: UUID, contact_id: UUID, payload: dict) -> None:
        """Синхронизирует contact_emails и contact_phones с payload."""
        # Удаляем старые
        from sqlalchemy import delete
        await self._repo._s.execute(delete(ContactEmail).where(ContactEmail.contact_id == contact_id))
        await self._repo._s.execute(delete(ContactPhone).where(ContactPhone.contact_id == contact_id))

        # Вставляем новые
        for e in payload.get("emails", []) or []:
            if not e.get("value"):
                continue
            self._repo._s.add(ContactEmail(
                tenant_id=tenant_id,
                contact_id=contact_id,
                value=e["value"],
                type=e.get("type", "unknown"),
                is_primary=e.get("is_primary", False),
                is_verified=e.get("is_verified", False),
                confidence=e.get("confidence", 0.0),
                evidence=e.get("evidence", []),
            ))
        for p in payload.get("phones", []) or []:
            if not p.get("value"):
                continue
            self._repo._s.add(ContactPhone(
                tenant_id=tenant_id,
                contact_id=contact_id,
                value=p["value"],
                type=p.get("type", "unknown"),
                is_primary=p.get("is_primary", False),
                is_whatsapp=p.get("is_whatsapp", False),
                is_telegram=p.get("is_telegram", False),
                confidence=p.get("confidence", 0.0),
                evidence=p.get("evidence", []),
            ))
        await self._repo._s.flush()
```

**Важно:** `_sync_emails_phones` — удаляет и пересоздаёт. Это просто и корректно, потому что emails/phones не имеют истории. Если понадобится история — переделаем.

### `routes_contacts.py`

```python
@router.post("", response_model=ContactUpsertResult, status_code=201)
async def upsert_contact(...):
    contact, action = await svc.upsert(...)
    if contact is None:
        # blocked
        return JSONResponse(
            {"status": "blocked", "reason": action.split(":", 1)[1]},
            status_code=409,
        )
    return ContactUpsertResult(
        contact=ContactRead.model_validate(contact, from_attributes=True),
        action=action,
    )


@router.post("/{contact_id}/status", response_model=ContactRead)
async def update_status(...):
    ...


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(...): ...


@router.get("", response_model=list[ContactRead])
async def list_contacts(...): ...


@router.post("/bulk", response_model=ContactBulkResult)
async def bulk_upsert(...): ...
```

### Схемы

```python
class ContactUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict
    status: str = "candidate"


class ContactRead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    tenant_id: UUID
    company_id: UUID | None
    fingerprint: str
    status: str
    payload: dict
    last_contacted_at: datetime | None
    last_reply_at: datetime | None
    replied_positive: bool
    schema_version: str
    created_at: datetime
    updated_at: datetime


class ContactUpsertResult(BaseModel):
    contact: ContactRead
    action: str


class ContactStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(candidate|approved|contacted|replied|qualified|disqualified|unsubscribed|bounced|archived)$")


class ContactBulkUpsert(BaseModel):
    items: list[ContactUpsert] = Field(min_length=1, max_length=500)


class ContactBulkResult(BaseModel):
    created: int
    updated: int
    merged: int
    blocked: int
    results: list[ContactUpsertResult]
    errors: list[dict]
```

### Тесты

`tests/test_contacts_api.py`:

```python
@pytest.mark.asyncio
async def test_upsert_contact_creates(client, headers, company_id):
    payload = {
        "full_name": {"value": "Иван Петров", "confidence": 1.0, "evidence": []},
        "company_id": company_id,  # передаём через payload? нет, через отдельное поле
        "emails": [{"value": "ivan@example.com", "type": "work", "is_primary": True, "confidence": 0.9, "evidence": []}],
        "phones": [],
        "position": {"value": "CTO", "confidence": 0.9, "evidence": []},
        "role_category": "decision_maker",
        "seniority": "c_level",
    }
    resp = await client.post(
        "/contacts",
        json={"payload": payload},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["action"] == "created"


@pytest.mark.asyncio
async def test_upsert_contact_merges_by_email(client, headers):
    p1 = {"full_name": {"value": "Иван Петров", "confidence": 1.0, "evidence": []}, "emails": [{"value": "ivan@x.com", "confidence": 0.9, "is_primary": True, "type": "work", "evidence": []}], "phones": []}
    p2 = {"full_name": {"value": "Иван Петров", "confidence": 1.0, "evidence": []}, "position": {"value": "CTO", "confidence": 0.9, "evidence": []}, "emails": [{"value": "ivan@x.com", "confidence": 0.9, "is_primary": True, "type": "work", "evidence": []}], "phones": []}

    r1 = await client.post("/contacts", json={"payload": p1}, headers={**headers, "Idempotency-Key": "c1"})
    r2 = await client.post("/contacts", json={"payload": p2}, headers={**headers, "Idempotency-Key": "c2"})
    assert r1.json()["contact"]["id"] == r2.json()["contact"]["id"]


@pytest.mark.asyncio
async def test_upsert_blocked_by_stoplist(client, headers):
    # Добавляем в stop-list
    await client.post("/stoplist", json={"kind": "email", "value": "blocked@x.com", "reason": "unsubscribed"}, headers={**headers, "Idempotency-Key": "sl1"})
    # Пытаемся создать контакт
    payload = {"full_name": {"value": "X", "confidence": 1.0, "evidence": []}, "emails": [{"value": "blocked@x.com", "confidence": 1.0, "is_primary": True, "type": "work", "evidence": []}], "phones": []}
    resp = await client.post("/contacts", json={"payload": payload}, headers={**headers, "Idempotency-Key": "c1"})
    assert resp.status_code == 409
    assert resp.json()["status"] == "blocked"
    assert resp.json()["reason"] == "unsubscribed"


@pytest.mark.asyncio
async def test_update_status_unsubscribed_adds_to_stoplist(client, headers):
    payload = {"full_name": {"value": "X", "confidence": 1.0, "evidence": []}, "emails": [{"value": "y@x.com", "confidence": 1.0, "is_primary": True, "type": "work", "evidence": []}], "phones": []}
    create = await client.post("/contacts", json={"payload": payload}, headers=headers)
    cid = create.json()["contact"]["id"]

    await client.post(f"/contacts/{cid}/status", json={"status": "unsubscribed"}, headers={**headers, "Idempotency-Key": "s1"})

    # Проверяем stop-list
    sl = await client.get("/stoplist", headers=headers)
    values = [e["value"] for e in sl.json()]
    assert "y@x.com" in values
```

## Acceptance criteria

```bash
uv run pytest services/contact-store/tests/test_contacts_api.py -v
# Ожидание: все passed

# E2E — создание контакта
curl -X POST https://contact-store.dev.aitler.ru/contacts \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: c1" \
  -d '{"payload":{"full_name":{"value":"Иван Петров","confidence":1.0,"evidence":[]},"emails":[{"value":"ivan@example.com","type":"work","is_primary":true,"confidence":0.9,"evidence":[]}],"phones":[],"role_category":"decision_maker","seniority":"c_level"}}' | jq .
# Ожидание: action: "created"

# E2E — блокировка stop-list
curl -X POST https://contact-store.dev.aitler.ru/stoplist \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: sl1" \
  -H "Content-Type: application/json" \
  -d '{"kind":"email","value":"blocked@example.com","reason":"unsubscribed"}'

curl -X POST https://contact-store.dev.aitler.ru/contacts \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: c2" \
  -H "Content-Type: application/json" \
  -d '{"payload":{"full_name":{"value":"X","confidence":1.0,"evidence":[]},"emails":[{"value":"blocked@example.com","confidence":1.0,"is_primary":true,"type":"work","evidence":[]}],"phones":[]}}' \
  -w "\n%{http_code}\n"
# Ожидание: 409, {"status": "blocked", "reason": "unsubscribed"}
```

## Подсказки

- **Stop-list проверяется до fingerprint.** Если email заблокирован — не создаём вообще.
- **`_sync_emails_phones`** — простой подход: удалить и пересоздать. Для больших объёмов можно оптимизировать diff'ом, но пока не нужно.
- **`company_id`** в payload контакта — опционально. Если контакт без компании, `company_id=None`.
- **`update_status`** — единственный способ добавить в stop-list через API. При `unsubscribed` — автоматически.

## Анти-паттерны

- ❌ Не создавать контакт, если email/phone в stop-list.
- ❌ Не забывать синхронизировать `contact_emails`/`contact_phones` при каждом upsert.
- ❌ Не позволять дубликат email в разных контактах одного тенанта — unique constraint защитит, но нужно корректно обработать ошибку.
- ❌ Не забывать обновлять `company.contacts_count` при создании/удалении контакта.

---

# Задача 2A.7 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-2a/2a.7-tests.md`

## Цель

Довести покрытие до 90%+, написать E2E-тест полного цикла (создать компанию → контакты → bulk → stop-list → проверить события), обновить CI.

## Зависимости

2A.1–2A.6.

## Что создать

### `tests/conftest.py`

По образцу `brief-service`. Fake-llm-gateway не нужен (contact-store не вызывает LLM).

### `tests/test_e2e.py`

```python
@pytest.mark.asyncio
@pytest.mark.slow
async def test_full_company_contact_flow(client, headers, tenant_id):
    # 1. Создать компанию
    company_payload = {
        "name": {"value": "ООО Ромашка", "confidence": 1.0, "evidence": []},
        "domain": {"value": "romashka.ru", "confidence": 1.0, "evidence": []},
        "industry": {"value": "Производство", "confidence": 0.9, "evidence": []},
        "size_estimate": {"employee_range": "smb"},
    }
    r = await client.post("/companies", json={"payload": company_payload}, headers=headers)
    assert r.status_code == 201
    company_id = r.json()["company"]["id"]

    # 2. Создать контакт
    contact_payload = {
        "full_name": {"value": "Иван Петров", "confidence": 1.0, "evidence": []},
        "position": {"value": "Генеральный директор", "confidence": 0.9, "evidence": []},
        "emails": [{"value": "ivan@romashka.ru", "type": "work", "is_primary": True, "confidence": 0.9, "evidence": []}],
        "phones": [{"value": "+79001234567", "type": "work", "is_primary": True, "confidence": 0.8, "evidence": []}],
        "role_category": "decision_maker",
        "seniority": "c_level",
        "company_id": company_id,
    }
    r = await client.post("/contacts", json={"payload": contact_payload}, headers={**headers, "Idempotency-Key": "c1"})
    assert r.status_code == 201
    contact_id = r.json()["contact"]["id"]

    # 3. Проверить, что contacts_count обновился
    r = await client.get(f"/companies/{company_id}", headers=headers)
    assert r.json()["contacts_count"] == 1

    # 4. Повторный upsert контакта — merge
    r = await client.post("/contacts", json={"payload": contact_payload}, headers={**headers, "Idempotency-Key": "c2"})
    assert r.json()["contact"]["id"] == contact_id

    # 5. Bulk upsert 10 контактов
    items = [
        {"payload": {
            "full_name": {"value": f"Контакт {i}", "confidence": 1.0, "evidence": []},
            "emails": [{"value": f"contact{i}@test.com", "confidence": 1.0, "is_primary": True, "type": "work", "evidence": []}],
            "phones": [],
        }}
        for i in range(10)
    ]
    r = await client.post("/contacts/bulk", json={"items": items}, headers={**headers, "Idempotency-Key": "bulk-1"})
    assert r.status_code == 200
    assert r.json()["created"] == 10

    # 6. Один из них в stop-list — не создаётся
    await client.post("/stoplist", json={"kind": "email", "value": "blocked@test.com", "reason": "manual"}, headers={**headers, "Idempotency-Key": "sl1"})
    r = await client.post("/contacts", json={"payload": {
        "full_name": {"value": "Blocked", "confidence": 1.0, "evidence": []},
        "emails": [{"value": "blocked@test.com", "confidence": 1.0, "is_primary": True, "type": "work", "evidence": []}],
        "phones": [],
    }}, headers={**headers, "Idempotency-Key": "c3"})
    assert r.status_code == 409

    # 7. Unsubscribe → попадает в stop-list
    r = await client.post(f"/contacts/{contact_id}/status", json={"status": "unsubscribed"}, headers={**headers, "Idempotency-Key": "s1"})
    assert r.status_code == 200

    r = await client.get("/stoplist", headers=headers)
    values = [e["value"] for e in r.json()]
    assert "ivan@romashka.ru" in values

    # 8. RLS: другой тенант не видит
    other = {"X-Tenant-ID": "00000000-0000-0000-0000-000000000099"}
    r = await client.get(f"/contacts/{contact_id}", headers=other)
    assert r.status_code == 404

    # 9. События в NATS (проверяется отдельно через nats-cli)
```

### Обновить CI

Добавить `contact-store` в matrix в `.github/workflows/ci.yml`.

### Обновить `scripts/migrate.sh` и `seed-sandbox.sh`

`contact-store` уже добавлен в 2A.1. Проверить.

## Acceptance criteria

```bash
uv run pytest services/contact-store/tests/ -v --cov=contact_store --cov-report=term-missing
# Ожидание: coverage >= 90%, все passed

uv run mypy services/contact-store
uv run ruff check services/contact-store

# E2E на dev
# См. test_e2e выше — все шаги проходят

# События в NATS
bash scripts/nats-cli.sh stream view CONTACTS --last 30 | grep -E "company\.(created|updated|merged)|contact\.(created|updated|merged|unsubscribed)"
# Ожидание: все типы

# CI
git push origin develop
# GitHub Actions — все зелёные
```

## Подсказки

- **Fake-LLM не нужен.** contact-store не вызывает LLM.
- **Тестовая БД** — отдельная `outreach_test`, сносится в fixture.
- **Порядок в E2E** — важен, тест последовательный.

## Анти-паттерны

- ❌ Не делать тесты, зависящие от глобального состояния.
- ❌ Не забывать `Idempotency-Key` в POST-тестах.
- ❌ Не делать E2E зависимым от внешних сервисов (только Postgres + NATS).

---

## Финальная E2E-проверка Спринта 2A

```bash
# 0. Setup
export TENANT="<sandbox_id>"
export BASE="https://contact-store.dev.aitler.ru"

# 1. Создать компанию
COMPANY=$(curl -sX POST $BASE/companies \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-c1" \
  -d '{
    "payload": {
      "name": {"value": "ООО Ромашка", "confidence": 1.0, "evidence": []},
      "domain": {"value": "romashka.ru", "confidence": 1.0, "evidence": []},
      "industry": {"value": "Производство", "confidence": 0.9, "evidence": []}
    }
  }')
COMPANY_ID=$(echo $COMPANY | jq -r .company.id)
echo "Company: $COMPANY_ID"

# 2. Повторно — должен быть merge
curl -sX POST $BASE/companies \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-c2" \
  -d '{
    "payload": {
      "name": {"value": "Ромашка", "confidence": 1.0, "evidence": []},
      "domain": {"value": "https://www.romashka.ru", "confidence": 1.0, "evidence": []},
      "signals": [{"type": "news", "summary": "Новое оборудование", "source_url": "https://news.ru/1", "detected_at": "2026-09-30T10:00:00Z", "relevance_score": 0.8}]
    }
  }' | jq .action
# Ожидание: "merged"

# 3. Создать контакт
CONTACT=$(curl -sX POST $BASE/contacts \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-ct1" \
  -d '{
    "payload": {
      "full_name": {"value": "Иван Петров", "confidence": 1.0, "evidence": []},
      "position": {"value": "Генеральный директор", "confidence": 0.9, "evidence": []},
      "emails": [{"value": "ivan@romashka.ru", "type": "work", "is_primary": true, "confidence": 0.9, "evidence": []}],
      "phones": [{"value": "+79001234567", "type": "work", "is_primary": true, "confidence": 0.8, "evidence": []}],
      "role_category": "decision_maker",
      "seniority": "c_level",
      "company_id": "'$COMPANY_ID'"
    }
  }')
CONTACT_ID=$(echo $CONTACT | jq -r .contact.id)
echo "Contact: $CONTACT_ID"

# 4. contacts_count компании
curl -s -H "X-Tenant-ID: $TENANT" $BASE/companies/$COMPANY_ID | jq .contacts_count
# Ожидание: 1

# 5. Bulk 20 контактов
curl -sX POST $BASE/contacts/bulk \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-bulk" \
  -d '{
    "items": [
      {"payload": {"full_name": {"value": "Контакт '$i'", "confidence": 1.0, "evidence": []}, "emails": [{"value": "c'$i'@romashka.ru", "confidence": 1.0, "is_primary": true, "type": "work", "evidence": []}], "phones": [], "company_id": "'$COMPANY_ID'"}}
    ]
  }' 2>/dev/null || \
curl -sX POST $BASE/contacts/bulk \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-bulk" \
  -d "{\"items\":[$(for i in $(seq 1 20); do echo '{"payload":{"full_name":{"value":"Контакт '$i'","confidence":1.0,"evidence":[]},"emails":[{"value":"c'$i'@romashka.ru","confidence":1.0,"is_primary":true,"type":"work","evidence":[]}],"phones":[],"company_id":"'$COMPANY_ID'"}}'; done | paste -sd ',' -)]}" | jq .

# 6. Остановить stop-list
curl -sX POST $BASE/stoplist \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-sl1" \
  -d '{"kind": "email", "value": "blocked@test.com", "reason": "manual"}' | jq .

# 7. Попытка создать контакт с заблокированным email — 409
curl -sX POST $BASE/contacts \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-ct-blocked" \
  -d '{"payload": {"full_name": {"value": "X", "confidence": 1.0, "evidence": []}, "emails": [{"value": "blocked@test.com", "confidence": 1.0, "is_primary": true, "type": "work", "evidence": []}], "phones": []}}' \
  -w "\n%{http_code}\n"
# Ожидание: 409, {"status": "blocked", "reason": "manual"}

# 8. Unsubscribe контакта — попадёт в stop-list
curl -sX POST $BASE/contacts/$CONTACT_ID/status \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-status" \
  -d '{"status": "unsubscribed"}' | jq .status
# Ожидание: "unsubscribed"

# 9. Проверить stop-list
curl -s -H "X-Tenant-ID: $TENANT" $BASE/stoplist | jq '.[].value'
# Ожидание: blocked@test.com, ivan@romashka.ru

# 10. RLS: другой тенант не видит
OTHER="00000000-0000-0000-0000-000000000000"
curl -s -H "X-Tenant-ID: $OTHER" $BASE/contacts/$CONTACT_ID -w "\n%{http_code}\n"
# Ожидание: 404

# 11. События в NATS
bash scripts/nats-cli.sh stream view CONTACTS --last 50 | grep -E "company\.(created|merged)|contact\.(created|merged|unsubscribed)"
# Ожидание: все типы

# 12. CI
git push origin develop
# GitHub Actions — зелёные
```

**Если все 12 пунктов проходят — Спринт 2A закрыт.**

---

## Проверка: что я перепроверил

- [x] Порядок задач: 2A.1 → 2A.2 → 2A.3 → 2A.4 → 2A.5 → 2A.6 → 2A.7, зависимости соблюдены.
- [x] Модели точно соответствуют `docs/contracts.md` разделы 3 и 4.
- [x] Fingerprint детерминированный, приоритеты корректны (ИНН → домен → имя).
- [x] Merger не мутирует исходные dict'ы (deepcopy везде).
- [x] Evidence объединяется без потерь.
- [x] Primary email/phone пересчитывается после merge.
- [x] Stop-list: RLS учитывает глобальные записи (tenant_id IS NULL).
- [x] ContactEmail/ContactPhone — вынесены, синхронизируются при upsert.
- [x] Unique constraints защищают от дубликатов email/phone в рамках тенанта.
- [x] Upsert сначала по fingerprint, потом по домену/email/phone — избегаем дубликатов.
- [x] События: company.created/updated/merged, contact.created/updated/merged/unsubscribed.
- [x] Стрим CONTACTS добавлен в NATS.
- [x] RLS на всех таблицах, кроме stoplist (специальная политика).
- [x] Bulk — синхронный, до 500 записей.
- [x] E2E тест покрывает весь цикл.
- [x] Mypy strict, ruff, pytest — везде.
- [x] Никаких `print`, `time.sleep`, `datetime.utcnow`.

---

## Что дальше (Спринт 2B)

После закрытия 2A переходим к **`icp-service`** — изолированному LLM-сервису, который превращает Brief в ICP с сегментами. Это проще, чем 2A, но критично для 2C (sourcing).

Задачи 2B выдам, когда 2A будет закрыт.

**Что от тебя нужно сейчас:**
1. Разложить эти 7 задач по файлам в `docs/tasks/sprint-2a/`.
2. Дать агенту: «Начинай с 2A.1, иди по порядку, после каждой задачи проверяй acceptance criteria».
3. Сообщить мне, когда 2A закрыт (или если агент застрял).

Если хочешь что-то поправить в задачах сейчас — скажи.
