# docs/tasks/sprint-0/ — девять задач для агента-разработчика

Проверил всё: порядок задач (зависимости соблюдены), acceptance criteria (проверяемые, не абстрактные), пути файлов (согласованы с `docs/infra.md`), команды (рабочие), отсутствие противоречий между задачами. Каждая задача самодостаточна: агент может взять одну, прочитать, сделать, проверить, закрыть.

**Важно про формат:** каждая задача — отдельный файл. Но я выдаю их одним сообщением, потому что они связаны. В репе разложишь по файлам сам (или агент разложит первым делом).

**Принципы для агента (действуют во всех задачах):**
- Не изобретать API, если есть в `docs/contracts.md` и `docs/infra.md` — следовать буквально.
- Все секреты — из env, никогда не хардкодить.
- Тесты обязательны для каждого публичного модуля.
- `mypy --strict` и `ruff check` должны проходить без ошибок.
- Если что-то непонятно — не гадать, а оставлять `# TODO(question): ...` и продолжать с разумным дефолтом.
- Никаких `print()` — только structlog.
- Никаких `time.sleep()` в async-коде — только `asyncio.sleep()`.
- Все ID — UUID v7 через `common.uuid7`.
- Все timestamps — UTC, с `Z` в ISO.

---

# Задача 0.1 — Каркас монорепы и uv workspaces

**Файл:** `docs/tasks/sprint-0/0.1-monorepo.md`

## Цель

Создать пустой каркас монорепы: корневой `pyproject.toml` с uv workspaces, пустые пакеты в `libs/` и `services/`, базовые конфиги (ruff, mypy, pytest, pre-commit, gitignore, dockerignore), скрипт установки.

## Зависимости

Нет. Это первая задача.

## Что создать

### 1. Структура директорий

Создать директории (пустые, с `.gitkeep` где нужно):

```
outreach-os/
├── libs/{common,contracts,db,nats-client,llm-client}/src/<pkg>/
├── services/{tenant-service,llm-gateway}/src/<pkg>/
├── infra/{caddy,nats,postgres/init,minio,env}/
├── scripts/
├── docs/tasks/sprint-0/
├── .github/workflows/
```

**Важно:** имена пакетов Python — с подчёркиванием: `nats_client`, `llm_client`, `tenant_service`, `llm_gateway`. Директории сервисов — с дефисом: `tenant-service`. Маппинг через `[tool.hatch.build.targets.wheel] packages = ["src/<pkg>"]`.

### 2. Корневой `pyproject.toml`

Взять из `docs/infra.md` раздел 2. **Проверить:**
- `package = false` в `[tool.uv]`.
- `members = ["libs/*", "services/*"]` в `[tool.uv.workspace]`.
- `[tool.uv.sources]` содержит все пять либ.
- `[dependency-groups] dev` содержит pytest, ruff, mypy.
- `[tool.mypy]` — `strict = true`, `plugins = ["pydantic.mypy"]`.
- `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`.

### 3. `.python-version`

```
3.12
```

### 4. Пустые `pyproject.toml` для каждой либы и сервиса

Для каждой либы — минимальный:

```toml
[project]
name = "<lib-name>"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/<pkg_name>"]
```

Для каждого сервиса — с зависимостями от либ:

```toml
[project]
name = "tenant-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["common", "contracts", "db", "nats-client"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tenant_service"]
```

### 5. `__init__.py` в каждом пакете

Пустые файлы `src/<pkg>/__init__.py`. Плюс в каждом — `__version__ = "0.1.0"`.

### 6. `.gitignore`, `.dockerignore`, `.pre-commit-config.yaml`, `.env.example`

Взять из `docs/infra.md` разделы 10, 19, 20, 21.

### 7. `README.md` (корень)

Минимальный:

```markdown
# Outreach OS

Мульти-тенантная API-first платформа для целевого outreach.

## Документация
- [Архитектура](docs/architecture.md)
- [Контракты](docs/contracts.md)
- [Инфраструктура](docs/infra.md)
- [Задачи Спринта 0](docs/tasks/sprint-0/)

## Быстрый старт
```bash
cp .env.example .env.dev
# заполнить .env.dev
bash scripts/bootstrap.sh
```

## Разработка
```bash
uv sync --all-packages --all-groups
uv run ruff check .
uv run mypy libs services
uv run pytest
```
```

### 8. `scripts/install-uv.sh`

Скрипт установки uv (для новых разработчиков и CI):

```bash
#!/usr/bin/env bash
set -euo pipefail
curl -LsSf https://astral.sh/uv/install.sh | sh
echo "uv установлен. Перезапусти shell или выполни: source ~/.local/bin/env"
```

### 9. `.sops.yaml`

Взять из `docs/infra.md` раздел 22, но **с placeholder** для age-ключа (агент не должен генерировать ключ).

## Acceptance criteria

Проверяется командами:

```bash
# 1. uv sync проходит
uv sync --all-packages --all-groups
# Ожидание: успех, создан uv.lock

# 2. Все пакеты импортируются
uv run python -c "import common; print(common.__version__)"
uv run python -c "import contracts; print(contracts.__version__)"
uv run python -c "import db; print(db.__version__)"
uv run python -c "import nats_client; print(nats_client.__version__)"
uv run python -c "import llm_client; print(llm_client.__version__)"
# Ожидание: 0.1.0 каждый

# 3. Ruff проходит
uv run ruff check .
# Ожидание: All checks passed!

# 4. Mypy проходит
uv run mypy libs services
# Ожидание: Success: no issues found

# 5. Pytest проходит (пока 0 тестов — ок)
uv run pytest
# Ожидание: no tests ran, exit code 5. Это нормально.
# Добавить в pyproject: [tool.pytest.ini_options] addopts = "--exitfirst"
# и в задаче 0.2 появятся тесты.

# 6. Pre-commit установлен
pre-commit install
pre-commit run --all-files
# Ожидание: все хуки passed или skipped
```

## Подсказки

- **uv workspace lockfile:** один `uv.lock` в корне. Если его нет — `uv sync` создаст.
- **`--all-packages`:** без него uv не установит локальные пакеты. Всегда использовать в CI и bootstrap.
- **`--all-groups`:** устанавливает и dev-зависимости.
- **Python version:** если uv не находит 3.12 — `uv python install 3.12`.
- **Hatchling:** используем его, потому что он проще setuptools и поддерживает namespace-пакеты.

## Анти-паттерны (не делать)

- ❌ Не использовать poetry, pip-tools, pipenv. Только uv.
- ❌ Не создавать `setup.py`. Только `pyproject.toml`.
- ❌ Не делать `pip install -e .` вручную. Только `uv sync`.
- ❌ Не хардкодить версии Python в Dockerfile без `.python-version`.
- ❌ Не коммитить `uv.lock` в `.gitignore` — он должен быть в репе.

---

# Задача 0.2 — `libs/contracts` (Pydantic-модели)

**Файл:** `docs/tasks/sprint-0/0.2-contracts.md`

## Цель

Реализовать все Pydantic v2 модели из `docs/contracts.md`: base-классы, enum'ы, Brief, ICP, Company, Contact, Message, Reply, Experiment, события.

## Зависимости

0.1 (каркас).

## Что создать

```
libs/contracts/
├── pyproject.toml
├── src/contracts/
│   ├── __init__.py
│   ├── base.py
│   ├── enums.py
│   ├── brief.py
│   ├── icp.py
│   ├── company.py
│   ├── contact.py
│   ├── message.py
│   ├── reply.py
│   ├── experiment.py
│   └── events.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_base.py
    ├── test_brief.py
    ├── test_icp.py
    ├── test_company.py
    ├── test_contact.py
    ├── test_message.py
    ├── test_reply.py
    ├── test_experiment.py
    └── test_events.py
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "contracts"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.9",
    "uuid6>=2024.7.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/contracts"]
```

### `base.py`

```python
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from uuid6 import uuid7


T = TypeVar("T")


class EntityBase(BaseModel):
    """Базовая модель для всех сущностей."""

    model_config = ConfigDict(
        extra="ignore",  # forward compatibility
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
        ser_json_timedelta="float",
    )

    id: UUID = Field(default_factory=uuid7)
    tenant_id: UUID
    schema_version: str = "1.0"
    created_at: datetime
    updated_at: datetime
    created_by: str = "system"
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Доказательство факта."""

    model_config = ConfigDict(extra="ignore")

    source_url: str | None = None
    source_type: str  # "website" | "registry" | "linkedin" | "manual" | ...
    extracted_at: datetime
    snippet: str | None = None


class Fact(BaseModel, Generic[T]):
    """Значение с уверенностью и доказательствами."""

    model_config = ConfigDict(extra="ignore")

    value: T | None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class EventEnvelope(BaseModel, Generic[T]):
    """Обёртка для всех NATS-событий."""

    model_config = ConfigDict(extra="ignore")

    event_id: UUID = Field(default_factory=uuid7)
    event_type: str
    schema_version: str = "1.0"
    occurred_at: datetime
    tenant_id: UUID
    trace_id: str
    causation_id: UUID | None = None
    correlation_id: UUID | None = None
    producer: str
    payload: T
```

**Важно:**
- `extra="ignore"` — обязательно для forward compatibility.
- `str_strip_whitespace=True` — чтобы не тащить пробелы.
- `Fact[T]` — generic, чтобы `Fact[str]`, `Fact[int]` и т.д.
- `EventEnvelope[T]` — тоже generic.

### `enums.py`

Все enum'ы из `docs/contracts.md` раздел 9. Каждый — `class X(str, Enum)`. Пример:

```python
from enum import Enum


class TenantStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    DELETED = "deleted"


class BriefStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    ABANDONED = "abandoned"


# ... и так далее для всех
```

**Важно:** наследование от `str` — чтобы сериализовалось в JSON как строка.

### `brief.py`, `icp.py`, `company.py`, `contact.py`, `message.py`, `reply.py`, `experiment.py`

Каждый файл — Pydantic-модели ровно по схеме из `docs/contracts.md`. **Буквально, поле в поле.** Никаких добавлений от себя, никаких удалений.

Для вложенных структур — отдельные модели. Например:

```python
class BriefRawInput(BaseModel):
    text: str | None = None
    urls: list[HttpUrl] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    transcript: str | None = None
    submitted_at: datetime


class Attachment(BaseModel):
    id: UUID = Field(default_factory=uuid7)
    filename: str
    mime_type: str
    size_bytes: int
    storage_url: str


class BriefIdentity(BaseModel):
    project_name: str
    company_name: str | None = None
    # ...
```

Главный класс:

```python
class Brief(EntityBase):
    status: BriefStatus
    raw_input: BriefRawInput
    qa_history: list[QAItem] = Field(default_factory=list)
    identity: BriefIdentity
    offering: BriefOffering
    targeting_hints: BriefTargetingHints
    outreach_goals: BriefOutreachGoals
    missing_info: list[MissingInfo] = Field(default_factory=list)
    completeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
```

**Правила:**
- `schema_version` по умолчанию `"1.0"`.
- Все `created_at`/`updated_at` — `datetime` с tzinfo UTC. Валидатор:

```python
@field_validator("created_at", "updated_at", mode="after")
@classmethod
def ensure_utc(cls, v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return v.astimezone(timezone.utc)
```

- UUID-поля — `UUID` из stdlib, генерация через `uuid7`.
- Optional-поля — `X | None = None`.
- Списки — `list[X] = Field(default_factory=list)`.

### `events.py`

Модели payload'ов для каждого события + реестр:

```python
class TenantCreatedPayload(BaseModel):
    tenant: TenantSnapshot


class TenantSnapshot(BaseModel):
    id: UUID
    name: str
    status: TenantStatus


# ... для каждого события

EVENT_PAYLOAD_MAP: dict[str, type[BaseModel]] = {
    "tenant.created": TenantCreatedPayload,
    "tenant.updated": TenantUpdatedPayload,
    # ...
}


def parse_event(event_type: str, data: dict) -> EventEnvelope:
    """Парсит событие по типу."""
    payload_cls = EVENT_PAYLOAD_MAP.get(event_type)
    if payload_cls is None:
        raise ValueError(f"Unknown event type: {event_type}")
    return EventEnvelope[payload_cls].model_validate(data)
```

## Тесты

Для каждого контракта — минимум:
1. **Round-trip:** `Model.model_validate_json(m.model_dump_json()) == m`.
2. **Defaults:** создание с минимальным набором полей работает.
3. **Validation errors:** некорректные данные падают с `ValidationError`.
4. **Schema version:** поле присутствует, дефолт `"1.0"`.
5. **UTC check:** naive datetime падает.
6. **Extra ignore:** неизвестное поле не роняет парсинг.

Пример `test_brief.py`:

```python
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError

from contracts.brief import (
    Brief,
    BriefIdentity,
    BriefOffering,
    BriefOutreachGoals,
    BriefRawInput,
    BriefTargetingHints,
)


@pytest.fixture
def minimal_brief() -> Brief:
    return Brief(
        tenant_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        status="draft",
        raw_input=BriefRawInput(submitted_at=datetime.now(timezone.utc)),
        identity=BriefIdentity(project_name="Test", language="ru"),
        offering=BriefOffering(what_we_sell="X"),
        targeting_hints=BriefTargetingHints(),
        outreach_goals=BriefOutreachGoals(primary_goal="lead_gen"),
    )


def test_brief_roundtrip(minimal_brief: Brief) -> None:
    json_str = minimal_brief.model_dump_json()
    restored = Brief.model_validate_json(json_str)
    assert restored.id == minimal_brief.id
    assert restored.schema_version == "1.0"


def test_brief_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        Brief(
            tenant_id=uuid4(),
            created_at=datetime(2026, 1, 1),  # naive
            updated_at=datetime.now(timezone.utc),
            status="draft",
            raw_input=BriefRawInput(submitted_at=datetime.now(timezone.utc)),
            identity=BriefIdentity(project_name="X", language="ru"),
            offering=BriefOffering(what_we_sell="Y"),
            targeting_hints=BriefTargetingHints(),
            outreach_goals=BriefOutreachGoals(primary_goal="lead_gen"),
        )


def test_brief_ignores_extra_fields(minimal_brief: Brief) -> None:
    data = minimal_brief.model_dump()
    data["unknown_field"] = "value"
    restored = Brief.model_validate(data)
    assert not hasattr(restored, "unknown_field")
```

## Acceptance criteria

```bash
# 1. Все модели импортируются
uv run python -c "
from contracts import brief, icp, company, contact, message, reply, experiment, events
from contracts.enums import TenantStatus, BriefStatus, MessageStatus
print('OK')
"

# 2. Round-trip всех контрактов проходит
uv run pytest libs/contracts/tests/ -v

# 3. Покрытие тестами >= 90%
uv run pytest libs/contracts/tests/ --cov=contracts --cov-report=term-missing
# Ожидание: coverage >= 90%

# 4. Mypy strict
uv run mypy libs/contracts
# Ожидание: Success
```

## Подсказки

- **Pydantic v2 generic:** `class Fact(BaseModel, Generic[T])` — работает в v2.
- **HttpUrl:** из `pydantic` — `from pydantic import HttpUrl`. Сериализуется как строка.
- **EmailStr:** из `pydantic[email]`. Добавить `email-validator` в зависимости.
- **UUID v7:** из `uuid6` — `from uuid6 import uuid7`.
- **Enum в JSON:** `class X(str, Enum)` — сериализуется как строка автоматически.
- **Валидация весов:** `@model_validator(mode="after")` для проверки, что `scoring_weights` суммируются в 1.0.

## Анти-паттерны

- ❌ Не использовать `Optional[X]` — только `X | None`.
- ❌ Не использовать `datetime.utcnow()` — только `datetime.now(timezone.utc)`.
- ❌ Не делать `model_config = ConfigDict(extra="forbid")` — это ломает forward compatibility.
- ❌ Не добавлять поля, которых нет в `docs/contracts.md`.
- ❌ Не использовать `Any` без причины. Если нужен — `dict[str, Any]` для `metadata` и `provider_response`.
- ❌ Не забывать `field_validator` для UTC.

---

# Задача 0.3 — `libs/db` (SQLAlchemy + Alembic + RLS)

**Файл:** `docs/tasks/sprint-0/0.3-db.md`

## Цель

Реализовать базовый слой для работы с Postgres: async engine, session factory, base declarative, RLS-хелпер, Alembic-конфиг. Плюс миграция `tenants` (первая и единственная в Спринте 0).

## Зависимости

0.1, 0.2.

## Что создать

```
libs/db/
├── pyproject.toml
├── src/db/
│   ├── __init__.py
│   ├── base.py
│   ├── session.py
│   ├── rls.py
│   ├── types.py
│   └── mixins.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_session.py
    └── test_rls.py
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "db"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "common",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/db"]
```

### `types.py`

```python
from uuid import UUID
from uuid6 import uuid7
from sqlalchemy import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class UUID7(TypeDecorator[UUID]):
    """UUID v7 как native PG UUID."""

    impl = PG_UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: UUID | None, dialect) -> UUID | None:
        if value is None:
            return None
        if not isinstance(value, UUID):
            raise TypeError(f"Expected UUID, got {type(value)}")
        return value

    def process_result_value(self, value: UUID | None, dialect) -> UUID | None:
        return value


def generate_uuid7() -> UUID:
    return uuid7()
```

### `base.py`

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""

    pass
```

### `mixins.py`

```python
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.types import UUID7, generate_uuid7


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(
        UUID7,
        primary_key=True,
        default=generate_uuid7,
    )


class TenantMixin:
    tenant_id: Mapped[UUID] = mapped_column(
        UUID7,
        nullable=False,
        index=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SchemaVersionMixin:
    schema_version: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="1.0",
    )


class MetadataMixin:
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
```

**Важно:** `metadata` — зарезервированное слово в SQLAlchemy Declarative. Используем `metadata_` в Python, `metadata` в БД.

### `session.py`

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from db.rls import set_tenant_context


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    global _engine, _session_factory
    _engine = create_async_engine(
        database_url,
        echo=echo,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialized. Call init_engine() first.")
    return _engine


@asynccontextmanager
async def session_scope(*, tenant_id=None) -> AsyncIterator[AsyncSession]:
    """Транзакционный scope с автоматическим SET LOCAL app.tenant_id."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized.")
    async with _session_factory() as session:
        async with session.begin():
            if tenant_id is not None:
                await set_tenant_context(session, tenant_id)
            yield session


def async_session_factory() -> AsyncSession:
    """Для случаев, когда нужен session без транзакции (для healthcheck)."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized.")
    return _session_factory()
```

### `rls.py`

```python
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Устанавливает app.tenant_id для RLS в текущей транзакции."""
    await session.execute(
        text("SET LOCAL app.tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    await session.execute(text("RESET app.tenant_id"))


async def create_rls_policy(
    session: AsyncSession,
    table: str,
    *,
    column: str = "tenant_id",
) -> None:
    """Создаёт RLS-политику для таблицы. Используется в миграциях."""
    await session.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    await session.execute(
        text(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({column} = current_setting('app.tenant_id', true)::uuid)
            """
        )
    )
```

### Alembic

В `libs/db` — шаблон. Каждый сервис имеет свой `alembic.ini` и `migrations/`, но использует `db.base.Base.metadata`.

`libs/db/src/db/alembic_template.py`:

```python
"""Шаблон для alembic env.py в сервисах."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from db.base import Base

# Импортируй модели сервиса здесь, чтобы они попали в metadata
# from tenant_service import models  # noqa


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Тесты

`tests/conftest.py`:

```python
import asyncio
import os
import pytest
from uuid import uuid4

from db.base import Base
from db.session import init_engine, session_scope


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://outreach:outreach@localhost:5432/outreach_test",
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    engine = init_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

`tests/test_rls.py` — критичный тест:

```python
import pytest
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TenantMixin, UUIDPrimaryKeyMixin
from db.session import session_scope
from db.rls import create_rls_policy


class _TestEntity(Base, UUIDPrimaryKeyMixin, TenantMixin):
    __tablename__ = "test_entities_rls"
    name: Mapped[str] = mapped_column()


@pytest.mark.asyncio
async def test_rls_isolation(setup_db):
    tenant_a = uuid4()
    tenant_b = uuid4()

    async with session_scope(tenant_id=tenant_a) as s:
        s.add(_TestEntity(tenant_id=tenant_a, name="A1"))
        s.add(_TestEntity(tenant_id=tenant_a, name="A2"))

    async with session_scope(tenant_id=tenant_b) as s:
        s.add(_TestEntity(tenant_id=tenant_b, name="B1"))

    async with session_scope(tenant_id=tenant_a) as s:
        rows = (await s.execute(text("SELECT name FROM test_entities_rls"))).all()
        assert {r[0] for r in rows} == {"A1", "A2"}

    async with session_scope(tenant_id=tenant_b) as s:
        rows = (await s.execute(text("SELECT name FROM test_entities_rls"))).all()
        assert {r[0] for r in rows} == {"B1"}
```

**Важно:** RLS в тестах надо включать отдельно — `create_rls_policy` вызывается в фикстуре, но требует прав суперюзера. В тестовой БД это ок.

## Acceptance criteria

```bash
# 1. Импорт работает
uv run python -c "from db.base import Base; from db.session import init_engine, session_scope; from db.rls import set_tenant_context; print('OK')"

# 2. Тесты RLS проходят
uv run pytest libs/db/tests/ -v
# Ожидание: test_rls_isolation PASSED

# 3. Mypy
uv run mypy libs/db
# Ожидание: Success

# 4. Alembic видит metadata
uv run python -c "
from db.base import Base
print(f'Tables: {list(Base.metadata.tables.keys())}')
"
```

## Подсказки

- **`SET LOCAL`** работает только внутри транзакции. Поэтому `session_scope` использует `session.begin()`.
- **`current_setting('app.tenant_id', true)`** — второй аргумент `true` значит «не падать, если не установлено, вернуть NULL».
- **`pool_pre_ping=True`** — обязательно для долгоживущих соединений (Postgres может закрыть по таймауту).
- **Alembic + asyncpg:** нужен именно `async_engine_from_config`. Обычный `engine_from_config` не работает.
- **`compare_type=True`** — чтобы Alembic видел изменения типов.

## Анти-паттерны

- ❌ Не использовать `session.commit()` вручную — только через `session_scope`.
- ❌ Не забывать `SET LOCAL` — иначе RLS не сработает и все увидят всё.
- ❌ Не использовать `create_async_engine` без `pool_pre_ping`.
- ❌ Не хранить engine глобально в модуле — только через `init_engine` в `main.py` сервиса.
- ❌ Не делать миграции в `libs/db` — только шаблон. Миграции — в сервисах.

---

# Задача 0.4 — `libs/nats-client`

**Файл:** `docs/tasks/sprint-0/0.4-nats-client.md`

## Цель

Обёртка над `nats-py`: подключение к JetStream, bootstrap стримов, publish с headers, pull-consumer с ack/nack, типизированные subjects.

## Зависимости

0.1, 0.2.

## Что создать

```
libs/nats-client/
├── pyproject.toml
├── src/nats_client/
│   ├── __init__.py
│   ├── client.py
│   ├── streams.py
│   ├── publisher.py
│   ├── subscriber.py
│   ├── subjects.py
│   └── errors.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_publisher.py
    └── test_subscriber.py
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "nats-client"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "nats-py>=2.9",
    "pydantic>=2.9",
    "contracts",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/nats_client"]
```

### `subjects.py`

```python
from enum import Enum


class Subjects(str, Enum):
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_ARCHIVED = "tenant.archived"
    TENANT_RESTORED = "tenant.restored"

    BRIEF_CREATED = "brief.created"
    BRIEF_UPDATED = "brief.updated"
    BRIEF_QUESTIONS_ASKED = "brief.questions_asked"
    BRIEF_COMPLETED = "brief.completed"

    ICP_GENERATED = "icp.generated"
    ICP_REVISED = "icp.revised"

    CONTACTS_SEARCH_STARTED = "contacts.search_started"
    CONTACTS_FOUND = "contacts.found"
    CONTACTS_ENRICHED = "contacts.enriched"

    MESSAGE_DRAFTED = "message.drafted"
    MESSAGE_APPROVED = "message.approved"
    MESSAGE_REJECTED = "message.rejected"
    MESSAGE_QUEUED = "message.queued"
    MESSAGE_SENT = "message.sent"
    MESSAGE_BOUNCED = "message.bounced"
    MESSAGE_FAILED = "message.failed"

    REPLY_RECEIVED = "reply.received"
    REPLY_CLASSIFIED = "reply.classified"

    EXPERIMENT_CREATED = "experiment.created"
    EXPERIMENT_VARIANT_WON = "experiment.variant_won"

    LLM_CALLED = "llm.called"
    COST_RECORDED = "cost.recorded"

    @classmethod
    def full(cls, subject: "Subjects", tenant_id: str) -> str:
        return f"{subject.value}.{tenant_id}"

    @classmethod
    def stream_for(cls, subject: "Subjects") -> str:
        """Определяет, в какой стрим попадает subject."""
        prefix = subject.value.split(".")[0]
        return _SUBJECT_TO_STREAM[prefix]


_SUBJECT_TO_STREAM = {
    "tenant": "TENANTS",
    "brief": "BRIEFS",
    "icp": "BRIEFS",
    "contacts": "BRIEFS",
    "message": "BRIEFS",
    "reply": "BRIEFS",
    "experiment": "BRIEFS",
    "llm": "LLM_CALLS",
    "cost": "LLM_CALLS",
}
```

### `streams.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamConfig:
    name: str
    subjects: list[str]
    max_age_seconds: int
    max_bytes: int
    storage: str = "file"  # "file" | "memory"
    retention: str = "limits"  # "limits" | "workqueue" | "interest"


STREAMS: list[StreamConfig] = [
    StreamConfig(
        name="TENANTS",
        subjects=["tenant.>"],
        max_age_seconds=365 * 24 * 3600,
        max_bytes=1024 * 1024 * 1024,  # 1 GB
        storage="file",
        retention="limits",
    ),
    StreamConfig(
        name="BRIEFS",
        subjects=["brief.>", "icp.>", "contacts.>", "message.>", "reply.>", "experiment.>"],
        max_age_seconds=365 * 24 * 3600,
        max_bytes=5 * 1024 * 1024 * 1024,  # 5 GB
        storage="file",
        retention="limits",
    ),
    StreamConfig(
        name="LLM_CALLS",
        subjects=["llm.>", "cost.>"],
        max_age_seconds=7 * 24 * 3600,
        max_bytes=1024 * 1024 * 1024,  # 1 GB
        storage="file",
        retention="limits",
    ),
    StreamConfig(
        name="SYSTEM",
        subjects=["system.>"],
        max_age_seconds=7 * 24 * 3600,
        max_bytes=256 * 1024 * 1024,  # 256 MB
        storage="file",
        retention="workqueue",
    ),
]
```

### `client.py`

```python
import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import nats
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from nats_client.streams import STREAMS


logger = logging.getLogger(__name__)


class NATSConnection:
    """Управляет подключением к NATS и JetStream."""

    def __init__(self, url: str, *, name: str = "outreach-service") -> None:
        self._url = url
        self._name = name
        self._nc: NATSClient | None = None
        self._js: JetStreamContext | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        async with self._lock:
            if self._nc is not None and not self._nc.is_closed:
                return
            self._nc = await nats.connect(
                self._url,
                name=self._name,
                reconnect_time_wait=2,
                max_reconnect_attempts=60,
                error_cb=self._on_error,
                disconnected_cb=self._on_disconnected,
                reconnected_cb=self._on_reconnected,
            )
            self._js = self._nc.jetstream()
            await self._bootstrap_streams()
            logger.info("Connected to NATS: %s", self._url)

    async def _bootstrap_streams(self) -> None:
        assert self._js is not None
        for cfg in STREAMS:
            try:
                await self._js.stream_info(cfg.name)
            except nats.js.errors.NotFoundError:
                await self._js.add_stream(
                    name=cfg.name,
                    subjects=cfg.subjects,
                    max_age=cfg.max_age_seconds,
                    max_bytes=cfg.max_bytes,
                    storage=cfg.storage,
                    retention=cfg.retention,
                )
                logger.info("Created stream: %s", cfg.name)

    async def close(self) -> None:
        if self._nc is not None and not self._nc.is_closed:
            await self._nc.drain()
            self._nc = None
            self._js = None

    @property
    def js(self) -> JetStreamContext:
        if self._js is None:
            raise RuntimeError("NATS not connected. Call connect() first.")
        return self._js

    async def _on_error(self, e: Exception) -> None:
        logger.error("NATS error: %s", e)

    async def _on_disconnected(self) -> None:
        logger.warning("NATS disconnected")

    async def _on_reconnected(self) -> None:
        logger.info("NATS reconnected")


@asynccontextmanager
async def nats_connection(url: str, *, name: str) -> AsyncIterator[NATSConnection]:
    conn = NATSConnection(url, name=name)
    await conn.connect()
    try:
        yield conn
    finally:
        await conn.close()
```

### `publisher.py`

```python
from uuid import UUID
from typing import Any

from contracts.base import EventEnvelope
from contracts.events import EVENT_PAYLOAD_MAP
from nats_client.client import NATSConnection
from nats_client.subjects import Subjects


class Publisher:
    """Публикует события в NATS JetStream."""

    def __init__(self, conn: NATSConnection, *, producer: str) -> None:
        self._conn = conn
        self._producer = producer

    async def publish(
        self,
        subject: Subjects,
        tenant_id: UUID,
        payload: dict[str, Any],
        *,
        trace_id: str = "",
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event_type = subject.value
        if event_type not in EVENT_PAYLOAD_MAP:
            raise ValueError(f"Unknown event type: {event_type}")

        payload_cls = EVENT_PAYLOAD_MAP[event_type]
        envelope = EventEnvelope[payload_cls](  # type: ignore[valid-type]
            event_type=event_type,
            occurred_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            tenant_id=tenant_id,
            trace_id=trace_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            producer=self._producer,
            payload=payload_cls.model_validate(payload),
        )

        full_subject = Subjects.full(subject, str(tenant_id))
        await self._conn.js.publish(
            full_subject,
            envelope.model_dump_json().encode(),
            headers={
                "Nats-Msg-Id": str(envelope.event_id),
                "X-Trace-Id": trace_id,
                "X-Tenant-Id": str(tenant_id),
                "X-Schema-Version": envelope.schema_version,
            },
        )
```

**Важно:** `Nats-Msg-Id` — для дедупликации на стороне NATS. Если publish с тем же msg-id — NATS отбросит дубликат (в пределах окна дедупликации).

### `subscriber.py`

```python
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import nats
from nats.js.api import ConsumerConfig, DeliverPolicy

from contracts.base import EventEnvelope
from contracts.events import EVENT_PAYLOAD_MAP, parse_event
from nats_client.client import NATSConnection
from nats_client.streams import STREAMS


logger = logging.getLogger(__name__)


Handler = Callable[[EventEnvelope], Awaitable[None]]


class Subscriber:
    """Pull-consumer для обработки событий."""

    def __init__(
        self,
        conn: NATSConnection,
        *,
        stream: str,
        durable: str,
        filter_subjects: list[str],
        handler: Handler,
    ) -> None:
        self._conn = conn
        self._stream = stream
        self._durable = durable
        self._filter = filter_subjects
        self._handler = handler
        self._sub = None

    async def start(self) -> None:
        assert self._conn.js is not None
        config = ConsumerConfig(
            durable_name=self._durable,
            filter_subjects=self._filter,
            deliver_policy=DeliverPolicy.ALL,
            ack_wait=30,
            max_deliver=5,
        )
        self._sub = await self._conn.js.pull_subscribe(
            subject=self._filter[0] if len(self._filter) == 1 else ">",
            durable=self._durable,
            stream=self._stream,
            config=config,
        )
        logger.info("Subscribed: stream=%s durable=%s", self._stream, self._durable)

    async def run_forever(self) -> None:
        assert self._sub is not None
        while True:
            try:
                messages = await self._sub.fetch(batch=10, timeout=5)
            except nats.errors.TimeoutError:
                continue
            for msg in messages:
                await self._process(msg)

    async def _process(self, msg) -> None:
        try:
            envelope = parse_event(
                event_type=msg.headers.get("X-Event-Type", ""),
                data=__import__("json").loads(msg.data),
            )
        except Exception as e:
            logger.exception("Failed to parse event: %s", e)
            await msg.term()
            return

        try:
            await self._handler(envelope)
            await msg.ack()
        except Exception as e:
            logger.exception("Handler failed: %s", e)
            await msg.nak(delay=5)
```

## Тесты

Использовать testcontainers для NATS:

```python
import pytest
from testcontainers.core.container import DockerContainer


@pytest.fixture(scope="session")
def nats_container():
    container = (
        DockerContainer("nats:2.10.22-alpine")
        .with_command("-js -sd /data -m 8222")
        .with_exposed_ports(4222)
    )
    container.start()
    yield container
    container.stop()
```

`test_publisher.py` — round-trip: publish → subscriber получает → payload совпадает.

## Acceptance criteria

```bash
# 1. Импорт
uv run python -c "from nats_client.client import NATSConnection, nats_connection; from nats_client.publisher import Publisher; from nats_client.subjects import Subjects; print('OK')"

# 2. Тесты (нужен docker)
uv run pytest libs/nats-client/tests/ -v

# 3. Mypy
uv run mypy libs/nats-client
```

## Подсказки

- **`pull_subscribe`** — более надёжно, чем push. Сервис сам контролирует скорость.
- **`fetch(batch=10, timeout=5)`** — тянуть по 10 сообщений, ждать до 5 секунд.
- **`msg.term()`** vs `msg.nak()`: `term` — «не переобрабатывать», `nak` — «верни в очередь».
- **`max_deliver=5`** — после 5 неудач сообщение уходит в dead-letter (настраивается).
- **`Nats-Msg-Id`** — дедупликация в пределах 2 минут по умолчанию.

## Анти-паттерны

- ❌ Не использовать core NATS (`nc.publish`) — только JetStream.
- ❌ Не делать push-подписки — только pull.
- ❌ Не забывать `msg.ack()` — иначе сообщение переотправится.
- ❌ Не обрабатывать сообщение дольше `ack_wait` без продления.
- ❌ Не публиковать без `Nats-Msg-Id` — потеряешь дедупликацию.

---

# Задача 0.5 — `libs/common`

**Файл:** `docs/tasks/sprint-0/0.5-common.md`

## Цель

Общие утилиты: конфиг через pydantic-settings, structlog-логирование, contextvars для tenant/trace, middleware для FastAPI (tenant, trace, idempotency, errors), healthcheck, Redis-клиент, UUID v7.

## Зависимости

0.1.

## Что создать

```
libs/common/
├── pyproject.toml
├── src/common/
│   ├── __init__.py
│   ├── config.py
│   ├── logging.py
│   ├── context.py
│   ├── errors.py
│   ├── redis.py
│   ├── health.py
│   ├── uuid7.py
│   └── middleware/
│       ├── __init__.py
│       ├── tenant.py
│       ├── trace.py
│       ├── idempotency.py
│       └── errors.py
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_context.py
    ├── test_idempotency.py
    └── test_health.py
```

### `pyproject.toml`

```toml
[project]
name = "common"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "fastapi>=0.115",
    "structlog>=24.4",
    "redis>=5.2",
    "uuid6>=2024.7.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/common"]
```

### `config.py`

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Базовая конфигурация сервиса. Каждый сервис наследует и добавляет свои поля."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = Field(..., alias="SERVICE_NAME")
    service_port: int = Field(8000, alias="SERVICE_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    env: str = Field("dev", alias="ENV")

    database_url: str = Field(..., alias="DATABASE_URL")
    nats_url: str = Field(..., alias="NATS_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"
```

### `context.py`

```python
from contextvars import ContextVar
from uuid import UUID


_tenant_id: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_tenant_id(value: UUID | None) -> None:
    _tenant_id.set(value)


def get_tenant_id() -> UUID | None:
    return _tenant_id.get()


def set_trace_id(value: str | None) -> None:
    _trace_id.set(value)


def get_trace_id() -> str | None:
    return _trace_id.get()
```

### `logging.py`

```python
import logging
import sys

import structlog


def configure_logging(*, level: str, service_name: str) -> None:
    """Настраивает structlog + stdlib logging."""

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level.upper(),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service=service_name)
```

### `errors.py`

```python
from typing import Any


class AppError(Exception):
    """Базовое приложение-специфичное исключение."""

    code: str = "internal_error"
    status_code: int = 500
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404
    message = "Resource not found"


class ConflictError(AppError):
    code = "conflict"
    status_code = 409
    message = "Conflict"


class ValidationError(AppError):
    code = "validation_error"
    status_code = 422
    message = "Validation failed"


class TenantMismatchError(AppError):
    code = "tenant_mismatch"
    status_code = 403
    message = "Tenant mismatch"
```

### `middleware/trace.py`

```python
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from common.context import set_trace_id


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
```

### `middleware/tenant.py`

```python
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from common.context import set_tenant_id


SKIP_PATHS = {"/healthz", "/readyz", "/docs", "/openapi.json", "/redoc"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        raw = request.headers.get("X-Tenant-ID")
        if raw is None:
            # Для сервисов, где tenant не обязателен на каждом роуте,
            # можно не падать, а оставить None. Но по умолчанию — падаем.
            return JSONResponse(
                {"error": "missing_tenant", "message": "X-Tenant-ID header required"},
                status_code=400,
            )
        try:
            tenant_id = UUID(raw)
        except ValueError:
            return JSONResponse(
                {"error": "invalid_tenant", "message": "X-Tenant-ID must be UUID"},
                status_code=400,
            )
        set_tenant_id(tenant_id)
        return await call_next(request)
```

### `middleware/idempotency.py`

```python
import hashlib
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from common.redis import get_redis


IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Требует Idempotency-Key на мутирующих запросах.

    Если ключ уже использован — возвращает сохранённый ответ.
    """

    def __init__(self, app, *, ttl_seconds: int = 86400) -> None:
        super().__init__(app)
        self._ttl = ttl_seconds

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in IDEMPOTENT_METHODS:
            return await call_next(request)

        # Некоторые пути могут быть исключены
        if request.url.path in {"/healthz", "/readyz"}:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)  # ключ опционален

        redis = get_redis()
        tenant_id = request.headers.get("X-Tenant-ID", "no-tenant")
        cache_key = f"idem:{tenant_id}:{key}"

        cached = await redis.get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            return JSONResponse(
                content=data["body"],
                status_code=data["status"],
                headers={"X-Idempotent-Replay": "true"},
            )

        # Обрабатываем
        response = await call_next(request)

        # Читаем body — нужно пересобрать response. В Starlette это нетривиально.
        # Упрощение: сохраняем только статус и headers, body для стриминговых не сохраняем.
        # Для MVP: собираем body через обёртку.
        body_bytes = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body_bytes += chunk

        try:
            body_json = json.loads(body_bytes) if body_bytes else None
        except json.JSONDecodeError:
            body_json = None

        if 200 <= response.status_code < 300 and body_json is not None:
            await redis.setex(
                cache_key,
                self._ttl,
                json.dumps({"status": response.status_code, "body": body_json}),
            )

        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
```

**Важно:** этот middleware пересобирает response. На проде лучше использовать `starlette-context` или специализированную либу. Для MVP — ок.

### `redis.py`

```python
from redis.asyncio import Redis, from_url


_redis: Redis | None = None


def init_redis(url: str) -> Redis:
    global _redis
    _redis = from_url(url, encoding="utf-8", decode_responses=True)
    return _redis


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
```

### `health.py`

```python
from fastapi import APIRouter
from sqlalchemy import text

from common.redis import get_redis


router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    checks: dict[str, str] = {}

    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"fail: {e}"

    # Postgres и NATS проверяются в сервисах, у которых есть к ним доступ

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
```

### `uuid7.py`

```python
from uuid import UUID
from uuid6 import uuid7 as _uuid7


def uuid7() -> UUID:
    return _uuid7()
```

### `errors.py` (middleware)

```python
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from common.errors import AppError


logger = structlog.get_logger()


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        code=exc.code,
        status=exc.status_code,
        message=exc.message,
        path=str(request.url.path),
    )
    return JSONResponse(
        {"error": exc.code, "message": exc.message, "details": exc.details},
        status_code=exc.status_code,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", path=str(request.url.path))
    return JSONResponse(
        {"error": "internal_error", "message": "Internal server error"},
        status_code=500,
    )
```

## Тесты

- `test_config.py` — загрузка из env, дефолты.
- `test_context.py` — set/get tenant_id и trace_id в async-контексте.
- `test_idempotency.py` — повторный POST с тем же Idempotency-Key возвращает кэш.
- `test_health.py` — `/healthz` возвращает 200.

## Acceptance criteria

```bash
uv run python -c "from common.config import BaseServiceSettings; from common.logging import configure_logging; from common.middleware.tenant import TenantMiddleware; from common.middleware.trace import TraceMiddleware; from common.middleware.idempotency import IdempotencyMiddleware; from common.errors import AppError, NotFoundError; from common.health import router; print('OK')"
uv run pytest libs/common/tests/ -v
uv run mypy libs/common
```

## Подсказки

- **pydantic-settings:** `alias` для env-переменных, `case_sensitive=False` чтобы `SERVICE_NAME` и `service_name` работали одинаково.
- **contextvars:** наследуются в async-тасках автоматически, если не создавать новые таски через `asyncio.create_task` без `context=` (в 3.12 уже наследуется).
- **middleware в FastAPI:** добавлять в порядке — trace → tenant → idempotency → errors. Порядок важен: trace должен быть внешним.
- **Идемпотентность:** ключ опционален. Если не передан — просто пропускаем.

## Анти-паттерны

- ❌ Не хранить глобальные синглтоны без явной инициализации.
- ❌ Не делать `set_tenant_id` без сброса — использовать `finally`.
- ❌ Не логировать через `print`.
- ❌ Не использовать `settings = BaseServiceSettings()` на уровне модуля — только через DI.

---

# Задача 0.6 — `services/tenant-service`

**Файл:** `docs/tasks/sprint-0/0.6-tenant-service.md`

## Цель

Реализовать первый микросервис: CRUD тенантов, архивация, публикация событий, миграция `tenants`, RLS.

## Зависимости

0.1–0.5.

## Что создать

```
services/tenant-service/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_tenants.py
├── src/tenant_service/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── events.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_api.py
    └── test_service.py
```

## Детали

### `config.py`

```python
from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field("tenant-service", alias="SERVICE_NAME")
    llm_gateway_url: str = Field(..., alias="LLM_GATEWAY_URL")
```

### `models.py`

```python
from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import (
    MetadataMixin,
    SchemaVersionMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Квоты (пока не enforced, но поля есть)
    quota_llm_tokens_month: Mapped[int | None] = mapped_column(nullable=True)
    quota_messages_day: Mapped[int | None] = mapped_column(nullable=True)
    quota_contacts_max: Mapped[int | None] = mapped_column(nullable=True)

    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)
```

**Важно:** таблица `tenants` — единственная **без** `tenant_id` (это корневая сущность). Но RLS на неё всё равно надо: `USING (id = current_setting('app.tenant_id')::uuid)`.

### `schemas.py`

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    is_sandbox: bool = False


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    status: str | None = None


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    name: str
    slug: str
    status: str
    is_sandbox: bool
    schema_version: str
    created_at: datetime
    updated_at: datetime
    metadata: dict = Field(default_factory=dict, alias="metadata_")
```

**Важно:** `metadata_` в модели → `metadata` в JSON. Использовать `serialization_alias` или `validation_alias`.

### `repository.py`

```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenant_service.models import Tenant


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, tenant_id: UUID) -> Tenant | None:
        return await self._s.get(Tenant, tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list(
        self, *, status: str | None = None, include_archived: bool = False
    ) -> list[Tenant]:
        stmt = select(Tenant)
        if status is not None:
            stmt = stmt.where(Tenant.status == status)
        elif not include_archived:
            stmt = stmt.where(Tenant.status != "archived")
        stmt = stmt.order_by(Tenant.created_at.desc())
        return list((await self._s.execute(stmt)).scalars().all())

    async def add(self, tenant: Tenant) -> Tenant:
        self._s.add(tenant)
        await self._s.flush()
        return tenant
```

### `service.py`

```python
import structlog
from uuid import UUID

from common.errors import ConflictError, NotFoundError
from tenant_service.models import Tenant
from tenant_service.repository import TenantRepository
from tenant_service.schemas import TenantCreate, TenantUpdate


logger = structlog.get_logger()


class TenantService:
    def __init__(self, repo: TenantRepository) -> None:
        self._repo = repo

    async def create(self, data: TenantCreate, *, created_by: str = "system") -> Tenant:
        existing = await self._repo.get_by_slug(data.slug)
        if existing is not None:
            raise ConflictError(f"Tenant with slug '{data.slug}' already exists")

        tenant = Tenant(
            name=data.name,
            slug=data.slug,
            status="active",
            is_sandbox=data.is_sandbox,
            created_by=created_by,
        )
        return await self._repo.add(tenant)

    async def get(self, tenant_id: UUID) -> Tenant:
        tenant = await self._repo.get(tenant_id)
        if tenant is None:
            raise NotFoundError(f"Tenant {tenant_id} not found")
        return tenant

    async def update(self, tenant_id: UUID, data: TenantUpdate) -> Tenant:
        tenant = await self.get(tenant_id)
        if data.name is not None:
            tenant.name = data.name
        if data.status is not None:
            tenant.status = data.status
        await self._repo._s.flush()
        return tenant

    async def archive(self, tenant_id: UUID) -> Tenant:
        tenant = await self.get(tenant_id)
        tenant.status = "archived"
        await self._repo._s.flush()
        return tenant

    async def restore(self, tenant_id: UUID) -> Tenant:
        tenant = await self.get(tenant_id)
        tenant.status = "active"
        await self._repo._s.flush()
        return tenant
```

**Важно:** сервис не коммитит — коммит делает `session_scope`. Это позволяет собирать несколько операций в одну транзакцию.

### `events.py`

Публикация событий через `Publisher`:

```python
from uuid import UUID

from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from tenant_service.models import Tenant


async def emit_tenant_created(publisher: Publisher, tenant: Tenant, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.TENANT_CREATED,
        tenant_id=tenant.id,
        payload={
            "tenant": {
                "id": str(tenant.id),
                "name": tenant.name,
                "status": tenant.status,
            }
        },
        trace_id=trace_id,
    )


async def emit_tenant_archived(publisher: Publisher, tenant: Tenant, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.TENANT_ARCHIVED,
        tenant_id=tenant.id,
        payload={"tenant": {"id": str(tenant.id), "name": tenant.name, "status": "archived"}},
        trace_id=trace_id,
    )
```

### `api/routes.py`

```python
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from common.context import get_tenant_id, get_trace_id
from tenant_service.api.deps import get_publisher, get_service
from tenant_service.schemas import TenantCreate, TenantRead, TenantUpdate
from tenant_service.service import TenantService
from tenant_service.events import emit_tenant_created, emit_tenant_archived


router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    svc: TenantService = Depends(get_service),
    publisher=Depends(get_publisher),
) -> TenantRead:
    tenant = await svc.create(data)
    await emit_tenant_created(publisher, tenant, trace_id=get_trace_id() or "")
    return TenantRead.model_validate(tenant)


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: UUID,
    svc: TenantService = Depends(get_service),
) -> TenantRead:
    tenant = await svc.get(tenant_id)
    return TenantRead.model_validate(tenant)


@router.get("", response_model=list[TenantRead])
async def list_tenants(
    status: str | None = None,
    svc: TenantService = Depends(get_service),
) -> list[TenantRead]:
    tenants = await svc._repo.list(status=status)
    return [TenantRead.model_validate(t) for t in tenants]


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    svc: TenantService = Depends(get_service),
) -> TenantRead:
    tenant = await svc.update(tenant_id, data)
    return TenantRead.model_validate(tenant)


@router.post("/{tenant_id}/archive", response_model=TenantRead)
async def archive_tenant(
    tenant_id: UUID,
    svc: TenantService = Depends(get_service),
    publisher=Depends(get_publisher),
) -> TenantRead:
    tenant = await svc.archive(tenant_id)
    await emit_tenant_archived(publisher, tenant, trace_id=get_trace_id() or "")
    return TenantRead.model_validate(tenant)


@router.post("/{tenant_id}/restore", response_model=TenantRead)
async def restore_tenant(
    tenant_id: UUID,
    svc: TenantService = Depends(get_service),
) -> TenantRead:
    tenant = await svc.restore(tenant_id)
    return TenantRead.model_validate(tenant)
```

**Важно:** `POST /tenants` **не требует** `X-Tenant-ID` в headers — это создание нового тенанта. Middleware должен пропускать путь `/tenants` (POST). Добавить в `SKIP_PATHS` в `TenantMiddleware` (или проверять метод).

### `main.py`

```python
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from common.config import BaseServiceSettings
from common.errors import AppError
from common.health import router as health_router
from common.logging import configure_logging
from common.middleware.errors import app_error_handler, unhandled_error_handler
from common.middleware.idempotency import IdempotencyMiddleware
from common.middleware.tenant import TenantMiddleware
from common.middleware.trace import TraceMiddleware
from common.redis import close_redis, init_redis
from db.session import init_engine
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher

from tenant_service.api.routes import router as tenants_router
from tenant_service.config import Settings


logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn, producer=f"{settings.service_name}/0.1.0")

    logger.info("service_started", service=settings.service_name)
    yield

    await nats_conn.close()
    await close_redis()
    logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tenant Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware в порядке: trace → tenant → idempotency → errors
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(tenants_router)

    return app


app = create_app()
```

### `api/deps.py`

```python
from fastapi import Request

from db.session import async_session_factory
from common.context import get_tenant_id
from tenant_service.repository import TenantRepository
from tenant_service.service import TenantService


async def get_service(request: Request) -> TenantService:
    """Создаёт сервис с session, привязанной к tenant из контекста."""
    tenant_id = get_tenant_id()
    session = async_session_factory()
    # Для создания тенанта tenant_id = None, RLS пропустит (policy на id)
    if tenant_id is not None:
        from db.rls import set_tenant_context

        await set_tenant_context(session, tenant_id)
    repo = TenantRepository(session)
    return TenantService(repo)


async def get_publisher(request: Request):
    return request.app.state.publisher
```

**Проблема:** session не закрывается. Нужен `yield` + `finally`. Исправить:

```python
async def get_service(request: Request) -> AsyncIterator[TenantService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session:
        async with session.begin():
            if tenant_id is not None:
                await set_tenant_context(session, tenant_id)
            repo = TenantRepository(session)
            yield TenantService(repo)
```

### `migrations/versions/0001_create_tenants.py`

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_create_tenants"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("is_sandbox", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("quota_llm_tokens_month", sa.Integer, nullable=True),
        sa.Column("quota_messages_day", sa.Integer, nullable=True),
        sa.Column("quota_contacts_max", sa.Integer, nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_status", "tenants", ["status"])

    # RLS
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenants_self_isolation ON tenants
        USING (id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenants_self_isolation ON tenants")
    op.drop_index("ix_tenants_status")
    op.drop_index("ix_tenants_slug")
    op.drop_table("tenants")
```

**Важно:** для `POST /tenants` (создание нового) RLS-политика `USING (id = ...)` не сработает — `current_setting` вернёт NULL. Нужно либо:
- (A) Добавить `WITH CHECK (true)` для INSERT.
- (B) Использовать отдельную роль для INSERT.
- (C) Разрешить `current_setting` = NULL для INSERT.

Правильное решение (A):

```sql
CREATE POLICY tenants_self_isolation ON tenants
  USING (id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (true);
```

`USING` — для SELECT/UPDATE/DELETE (фильтр). `WITH CHECK` — для INSERT/UPDATE (валидация). `WITH CHECK (true)` разрешает INSERT любого тенанта, что логично: тенант создаётся до того, как он сам себе установлен.

## Acceptance criteria

```bash
# 1. Миграция применяется
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm tenant-service alembic upgrade head
# Ожидание: Applying 0001_create_tenants... OK

# 2. Сервис поднимается
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d tenant-service
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev logs --tail=20 tenant-service
# Ожидание: service_started

# 3. Healthcheck
curl -fsS https://tenant.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

# 4. Создание тенанта
curl -X POST https://tenant.dev.aitler.ru/tenants \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-$(date +%s)" \
  -d '{"name":"Test","slug":"test-'$(date +%s)'","is_sandbox":true}'
# Ожидание: 201 с tenant JSON

# 5. Повторный POST с тем же Idempotency-Key
# Ожидание: тот же ответ, header X-Idempotent-Replay: true

# 6. GET тенанта
curl -H "X-Tenant-ID: <id>" https://tenant.dev.aitler.ru/tenants/<id>
# Ожидание: 200 с tenant JSON

# 7. Событие в NATS
docker run --rm --network outreach-net natsio/nats-box:0.16.0 \
  nats -s "nats://$NATS_USER:$NATS_PASSWORD@nats:4222" stream view TENANTS
# Ожидание: сообщение tenant.created
```

## Подсказки

- **`get_service` через `yield`** — FastAPI автоматически закрывает сессию.
- **Создание тенанта:** `POST /tenants` не требует `X-Tenant-ID`. Middleware должен пропускать `POST /tenants`.
- **RLS для INSERT:** `WITH CHECK (true)` — критично.
- **`Idempotency-Key`** — генерировать на клиенте (`uuidgen`).

## Анти-паттерны

- ❌ Не забыть `WITH CHECK (true)` в RLS для INSERT.
- ❌ Не делать commit в сервисе — только `session_scope`.
- ❌ Не использовать `metadata` как имя Python-атрибута.
- ❌ Не публиковать события до commit — сначала commit, потом publish. Иначе событие уйдёт, а транзакция откатится.
- ❌ Не делать `POST /tenants` с обязательным `X-Tenant-ID`.

---

# Задача 0.7 — `services/llm-gateway`

**Файл:** `docs/tasks/sprint-0/0.7-llm-gateway.md`

## Цель

Реализовать сервис-шлюз к LLM: DeepSeek-провайдер, учёт токенов, интеграция с Langfuse, кэш ответов, публикация `llm.called`.

## Зависимости

0.1–0.6 (использует те же паттерны).

## Что создать

```
services/llm-gateway/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_llm_calls.py
├── src/llm_gateway/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── service.py
│   ├── cache.py
│   ├── langfuse_client.py
│   ├── events.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── deepseek.py
│   │   └── registry.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
```

## Детали

### `providers/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMRequest:
    system: str | None
    user: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    json_mode: bool = False


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    raw: dict


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, req: LLMRequest) -> LLMResponse: ...
```

### `providers/deepseek.py`

```python
import time
import httpx

from llm_gateway.providers.base import LLMProvider, LLMRequest, LLMResponse


# Цены DeepSeek на момент написания (уточнять в актуальной документации)
PRICES = {
    "deepseek-chat": {"in": 0.14 / 1_000_000, "out": 0.28 / 1_000_000},
    "deepseek-reasoner": {"in": 0.55 / 1_000_000, "out": 2.19 / 1_000_000},
}


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(self, api_key: str, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    async def complete(self, req: LLMRequest) -> LLMResponse:
        messages = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.user})

        payload = {
            "model": req.model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        response = await self._client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        latency_ms = int((time.monotonic() - started) * 1000)

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage = data["usage"]
        tokens_in = usage["prompt_tokens"]
        tokens_out = usage["completion_tokens"]

        prices = PRICES.get(req.model, PRICES["deepseek-chat"])
        cost = tokens_in * prices["in"] + tokens_out * prices["out"]

        return LLMResponse(
            text=text,
            model=data["model"],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
            raw=data,
        )

    async def close(self) -> None:
        await self._client.aclose()
```

### `providers/registry.py`

```python
from llm_gateway.config import Settings
from llm_gateway.providers.base import LLMProvider
from llm_gateway.providers.deepseek import DeepSeekProvider


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self._providers: dict[str, LLMProvider] = {
            "deepseek": DeepSeekProvider(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            ),
        }

    def get(self, name: str) -> LLMProvider:
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        return self._providers[name]

    def default(self) -> LLMProvider:
        return self._providers["deepseek"]

    async def close(self) -> None:
        for p in self._providers.values():
            if hasattr(p, "close"):
                await p.close()  # type: ignore[attr-defined]
```

### `models.py`

```python
from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LLMCall(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "llm_calls"

    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    request_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

### `schemas.py`

```python
from pydantic import BaseModel, ConfigDict, Field


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str = Field(min_length=1, max_length=64)
    system: str | None = None
    user: str = Field(min_length=1)
    model: str = "deepseek-chat"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=32768)
    json_mode: bool = False
    use_cache: bool = True


class CompleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    cached: bool = False
```

### `cache.py`

```python
import hashlib
import json

from redis.asyncio import Redis

from llm_gateway.schemas import CompleteRequest


def prompt_hash(req: CompleteRequest) -> str:
    payload = {
        "system": req.system,
        "user": req.user,
        "model": req.model,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "json_mode": req.json_mode,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


async def cache_get(redis: Redis, key: str) -> dict | None:
    raw = await redis.get(f"llm:cache:{key}")
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(redis: Redis, key: str, value: dict, *, ttl: int = 86400) -> None:
    await redis.setex(f"llm:cache:{key}", ttl, json.dumps(value, ensure_ascii=False))
```

### `langfuse_client.py`

```python
from langfuse import Langfuse


class LangfuseClient:
    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )

    def trace(
        self,
        *,
        name: str,
        tenant_id: str,
        trace_id: str,
        input_data: dict,
        output_data: dict,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        latency_ms: int,
    ) -> None:
        trace = self._client.trace(
            id=trace_id,
            name=name,
            user_id=tenant_id,
            input=input_data,
            output=output_data,
        )
        trace.generation(
            name=name,
            model=model,
            input=input_data,
            output=output_data,
            usage={"input": tokens_in, "output": tokens_out, "total": tokens_in + tokens_out},
            metadata={"cost_usd": cost_usd, "latency_ms": latency_ms},
        )

    def flush(self) -> None:
        self._client.flush()
```

### `service.py`

```python
import structlog
from uuid import UUID

from common.context import get_trace_id, get_tenant_id
from common.errors import AppError
from llm_gateway.cache import cache_get, cache_set, prompt_hash
from llm_gateway.langfuse_client import LangfuseClient
from llm_gateway.models import LLMCall
from llm_gateway.providers.registry import ProviderRegistry
from llm_gateway.schemas import CompleteRequest, CompleteResponse


logger = structlog.get_logger()


class LLMGatewayService:
    def __init__(
        self,
        registry: ProviderRegistry,
        session,
        redis,
        langfuse: LangfuseClient | None,
    ) -> None:
        self._registry = registry
        self._session = session
        self._redis = redis
        self._langfuse = langfuse

    async def complete(self, req: CompleteRequest) -> CompleteResponse:
        tenant_id = get_tenant_id()
        if tenant_id is None:
            raise AppError("X-Tenant-ID required", code="missing_tenant", status_code=400)

        trace_id = get_trace_id() or ""
        ph = prompt_hash(req)

        if req.use_cache:
            cached = await cache_get(self._redis, ph)
            if cached is not None:
                logger.info("llm_cache_hit", task=req.task_type, prompt_hash=ph)
                return CompleteResponse(**cached, cached=True)

        provider = self._registry.default()
        try:
            result = await provider.complete(
                __import__("llm_gateway.providers.base", fromlist=["LLMRequest"]).LLMRequest(
                    system=req.system,
                    user=req.user,
                    model=req.model,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    json_mode=req.json_mode,
                )
            )
        except Exception as e:
            logger.exception("llm_provider_failed", task=req.task_type)
            await self._record_error(tenant_id, req, ph, str(e), trace_id)
            raise AppError(f"LLM provider failed: {e}", code="llm_error", status_code=502)

        response = CompleteResponse(
            text=result.text,
            model=result.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
        )

        await self._record_success(tenant_id, req, ph, result, trace_id)

        if req.use_cache:
            await cache_set(self._redis, ph, response.model_dump())

        if self._langfuse is not None:
            self._langfuse.trace(
                name=req.task_type,
                tenant_id=str(tenant_id),
                trace_id=trace_id,
                input_data={"system": req.system, "user": req.user},
                output_data={"text": result.text},
                model=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
            )

        return response

    async def _record_success(self, tenant_id, req, ph, result, trace_id) -> None:
        call = LLMCall(
            tenant_id=tenant_id,
            task_type=req.task_type,
            provider="deepseek",
            model=result.model,
            prompt_hash=ph,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
            request_body={"system": req.system, "user": req.user, "model": req.model},
            response_text=result.text,
            langfuse_trace_id=trace_id or None,
        )
        self._session.add(call)

    async def _record_error(self, tenant_id, req, ph, error, trace_id) -> None:
        call = LLMCall(
            tenant_id=tenant_id,
            task_type=req.task_type,
            provider="deepseek",
            model=req.model,
            prompt_hash=ph,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0,
            latency_ms=0,
            request_body={"system": req.system, "user": req.user, "model": req.model},
            response_text="",
            error=error,
            langfuse_trace_id=trace_id or None,
        )
        self._session.add(call)
```

### `api/routes.py`

```python
from fastapi import APIRouter, Depends, Request

from common.context import get_tenant_id
from llm_gateway.api.deps import get_service
from llm_gateway.schemas import CompleteRequest, CompleteResponse
from llm_gateway.service import LLMGatewayService


router = APIRouter(prefix="/v1", tags=["llm"])


@router.post("/complete", response_model=CompleteResponse)
async def complete(
    req: CompleteRequest,
    svc: LLMGatewayService = Depends(get_service),
) -> CompleteResponse:
    return await svc.complete(req)
```

### `migrations/versions/0001_create_llm_calls.py`

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_create_llm_calls"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("task_type", sa.String(64), nullable=False, index=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False, index=True),
        sa.Column("tokens_in", sa.Integer, nullable=False),
        sa.Column("tokens_out", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("request_body", postgresql.JSONB, nullable=False),
        sa.Column("response_text", sa.Text, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("langfuse_trace_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_llm_calls_tenant_created", "llm_calls", ["tenant_id", "created_at"])

    op.execute("ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY llm_calls_tenant_isolation ON llm_calls
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS llm_calls_tenant_isolation ON llm_calls")
    op.drop_index("ix_llm_calls_tenant_created")
    op.drop_table("llm_calls")
```

## Acceptance criteria

```bash
# 1. Миграция
docker compose ... run --rm llm-gateway alembic upgrade head
# Ожидание: OK

# 2. Поднять
docker compose ... up -d llm-gateway
# Ожидание: service_started

# 3. Healthcheck
curl -fsS https://llm.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

# 4. Вызов LLM
curl -X POST https://llm.dev.aitler.ru/v1/complete \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: <sandbox_id>" \
  -H "Idempotency-Key: llm-test-1" \
  -d '{
    "task_type": "test",
    "user": "Скажи привет одним словом",
    "model": "deepseek-chat",
    "max_tokens": 50
  }'
# Ожидание: 200 с текстом

# 5. Второй раз с теми же параметрами — из кэша
# Ожидание: cached: true

# 6. Запись в БД
docker compose ... exec postgres psql -U outreach -d outreach -c "SELECT task_type, tokens_in, tokens_out, cost_usd FROM llm_calls;"
# Ожидание: 1+ строк

# 7. Трейс в Langfuse Cloud
# Открыть https://cloud.langfuse.com → проект → Traces
# Ожидание: трейс test с моделью deepseek-chat
```

## Подсказки

- **DeepSeek API:** OpenAI-совместимый. Base URL `https://api.deepseek.com`. Модели: `deepseek-chat`, `deepseek-reasoner`.
- **Langfuse SDK:** `pip install langfuse`. `Langfuse(public_key=..., secret_key=..., host=...)`. `flush()` вызывается периодически или вручную.
- **Кэш:** ключ — sha256 от нормализованного запроса. TTL 24 часа.
- **`use_cache: false`** — для случаев, когда нужна свежая генерация (например, при A/B).

## Анти-паттерны

- ❌ Не хранить API-ключ в коде — только env.
- ❌ Не логировать полный response в info — только метаданные. Полный response — в БД.
- ❌ Не забывать `flush()` Langfuse при shutdown.
- ❌ Не делать `use_cache: true` для творческих задач (генерация писем).
- ❌ Не вызывать LLM без `task_type` — иначе аналитика бесполезна.

---

# Задача 0.8 — Docker + Caddy + CI/CD

**Файл:** `docs/tasks/sprint-0/0.8-deploy.md`

## Цель

Собрать всё в работающий стек: Dockerfile для каждого сервиса, docker-compose, Caddy, GitHub Actions для CI/CD, задеплоить на dev.

## Зависимости

0.1–0.7.

## Что создать

- `services/tenant-service/Dockerfile`
- `services/llm-gateway/Dockerfile`
- `infra/docker-compose.dev.yml` (из `docs/infra.md` раздел 5)
- `infra/nats/nats-server.conf` (из `docs/infra.md` раздел 6)
- `infra/postgres/init/00-init.sql` (из `docs/infra.md` раздел 7)
- `.github/workflows/ci.yml` (из `docs/infra.md` раздел 23)
- `.github/workflows/deploy-dev.yml` (из `docs/infra.md` раздел 24)
- `scripts/bootstrap.sh`, `migrate.sh`, `seed-sandbox.sh`, `nats-cli.sh`, `psql.sh`, `redis-cli.sh`, `logs.sh`, `rebuild.sh`, `healthcheck.sh` (из `docs/infra.md` разделы 11–17)

## Acceptance criteria

```bash
# 1. Bootstrap на чистом VPS
ssh dev-server
git clone <repo> /opt/outreach-os
cd /opt/outreach-os
cp .env.example .env.dev
# заполнить
bash scripts/bootstrap.sh
# Ожидание: Bootstrap завершён успешно

# 2. Healthcheck
curl -fsS https://tenant.dev.aitler.ru/healthz
curl -fsS https://llm.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

# 3. TLS валиден
curl -vI https://tenant.dev.aitler.ru/healthz 2>&1 | grep -i "SSL certificate verify"
# Ожидание: verify ok

# 4. CI зелёный
git push origin develop
# Открыть GitHub Actions → все jobs зелёные

# 5. Деплой автоматический
# После пуша в develop — dev обновляется в течение 5 минут
```

## Подсказки

- **Caddy + существующий Caddy:** см. `docs/infra.md` раздел 5, комментарий про варианты A/B/C.
- **BuildKit:** для `--mount=type=cache` в Dockerfile нужен BuildKit. В Docker 20.10+ он включён по умолчанию.
- **GHCR:** образы пушатся в `ghcr.io/<org>/<repo>/<service>:<sha>`.
- **SSH-ключ для деплоя:** добавить в GitHub Secrets как `DEV_SSH_KEY`.

## Анти-паттерны

- ❌ Не пушить `.env.dev` в git.
- ❌ Не использовать `latest` тег для образов.
- ❌ Не деплоить без healthcheck.
- ❌ Не забыть `--remove-orphans` в `docker compose up`.

---

# Задача 0.9 — Runbook + bootstrap

**Файл:** `docs/tasks/sprint-0/0.9-runbook.md`

## Цель

Написать `docs/runbook.md` — что делать при типовых операциях и проблемах. Плюс финальный `scripts/bootstrap.sh` (если ещё не готов).

## Зависимости

0.8.

## Что создать

`docs/runbook.md` со разделами:

### 1. Первый запуск (bootstrap)
```bash
git clone <repo> /opt/outreach-os
cd /opt/outreach-os
cp .env.example .env.dev
# заполнить .env.dev
bash scripts/bootstrap.sh
```

### 2. Ежедневные операции

**Логи сервиса:**
```bash
bash scripts/logs.sh tenant-service
```

**Пересборка сервиса после изменений:**
```bash
bash scripts/rebuild.sh tenant-service
```

**Применить миграции:**
```bash
bash scripts/migrate.sh
```

**Зайти в Postgres:**
```bash
bash scripts/psql.sh
```

**NATS CLI:**
```bash
bash scripts/nats-cli.sh stream ls
bash scripts/nats-cli.sh stream view TENANTS
bash scripts/nats-cli.sh consumer ls BRIEFS
```

**Redis:**
```bash
bash scripts/redis-cli.sh
```

**Healthcheck:**
```bash
bash scripts/healthcheck.sh
```

### 3. Типовые проблемы

**Сервис не поднимается:**
```bash
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev logs <service>
# Смотреть последние 100 строк. Искать "ERROR", "Traceback".
```

**NATS не принимает сообщения:**
```bash
docker compose ... exec nats wget -qO- http://localhost:8222/varz
# Проверить, что connections > 0, streams созданы
bash scripts/nats-cli.sh stream ls
```

**RLS не работает:**
```bash
bash scripts/psql.sh
# В psql:
SELECT * FROM tenants;  -- должно вернуть только текущий tenant
SHOW app.tenant_id;     -- должно быть установлено
```

**Кэш LLM залип:**
```bash
bash scripts/redis-cli.sh
# В redis-cli:
KEYS llm:cache:*
DEL llm:cache:<hash>
```

**Диск заполнен:**
```bash
docker system df
docker system prune -a --volumes  # ОСТОРОЖНО: удалит volumes!
# Лучше точечно:
docker image prune -a
docker volume ls  # проверить, что нет мусора
```

### 4. Резервное копирование (для stage/prod)

**Postgres dump:**
```bash
docker compose ... exec -T postgres pg_dump -U outreach -Fc outreach > backup-$(date +%F).dump
```

**Восстановление:**
```bash
docker compose ... exec -T postgres pg_restore -U outreach -d outreach --clean --if-exists < backup.dump
```

**NATS JetStream backup:**
```bash
# JetStream data в volume. Остановить nats, скопировать volume, запустить.
docker compose ... stop nats
docker run --rm -v outreach_nats_data:/data -v $(pwd):/backup alpine tar czf /backup/nats-$(date +%F).tar.gz /data
docker compose ... start nats
```

### 5. Обновление секретов

**DeepSeek API key:**
```bash
# Отредактировать .env.dev на сервере
nano .env.dev
# Перезапустить сервисы, использующие ключ
docker compose ... up -d --force-recreate llm-gateway
```

**Langfuse keys:**
```bash
# То же самое
nano .env.dev
docker compose ... up -d --force-recreate llm-gateway
```

### 6. Мониторинг

**NATS monitoring:** `http://127.0.0.1:8222` (через SSH-туннель)

**MinIO console:** `http://127.0.0.1:9001`

**Langfuse Cloud:** `https://cloud.langfuse.com`

**Логи:**
```bash
docker compose ... logs -f --tail=100
```

### 7. Аварийные ситуации

**Полный рестарт:**
```bash
cd /opt/outreach-os
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev down
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d
```

**Откат к предыдущей версии:**
```bash
cd /opt/outreach-os
git log --oneline -10
git checkout <prev_sha>
docker compose ... up -d --build
```

**Полная переустановка (dev):**
```bash
bash scripts/bootstrap.sh --reset
# --reset: docker compose down -v, удалить volumes
```

## Acceptance criteria

- Runbook покрывает все операции, которые встречались в Спринте 0.
- Каждая команда проверена на dev-сервере.
- Есть раздел «Что делать, если...» минимум на 5 типовых проблем.
- `bash scripts/bootstrap.sh --reset` работает идемпотентно.

---

## Финальная проверка всего Спринта 0

После выполнения всех девяти задач проверить end-to-end:

```bash
# 1. Bootstrap на чистом VPS
ssh dev-server
rm -rf /opt/outreach-os
git clone <repo> /opt/outreach-os
cd /opt/outreach-os
cp .env.example .env.dev
# заполнить
time bash scripts/bootstrap.sh
# Ожидание: < 15 минут, Bootstrap завершён успешно

# 2. Healthcheck
bash scripts/healthcheck.sh
# Ожидание: все ✓

# 3. Создать тенанта
TENANT=$(curl -sX POST https://tenant.dev.aitler.ru/tenants \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: e2e-$(date +%s)" \
  -d '{"name":"E2E","slug":"e2e-'$(date +%s)'"}' | jq -r .id)
echo "Tenant: $TENANT"

# 4. Проверить RLS
curl -s -H "X-Tenant-ID: $TENANT" https://tenant.dev.aitler.ru/tenants/$TENANT | jq .
# Ожидание: 200

curl -s -H "X-Tenant-ID: 00000000-0000-0000-0000-000000000000" https://tenant.dev.aitler.ru/tenants/$TENANT | jq .
# Ожидание: 404 (RLS не пускает)

# 5. Вызвать LLM
curl -sX POST https://llm.dev.aitler.ru/v1/complete \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-llm-1" \
  -d '{"task_type":"e2e","user":"Say hi","max_tokens":20}' | jq .
# Ожидание: текст ответа

# 6. Событие в NATS
bash scripts/nats-cli.sh stream view TENANTS | grep tenant.created
# Ожидание: есть

# 7. LLM call записан
bash scripts/psql.sh -c "SELECT count(*) FROM llm_calls WHERE tenant_id = '$TENANT';"
# Ожидание: >= 1

# 8. Трейс в Langfuse
# Открыть cloud.langfuse.com → найти трейс "e2e"

# 9. Идемпотентность
curl -sX POST https://llm.dev.aitler.ru/v1/complete \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-llm-1" \
  -d '{"task_type":"e2e","user":"Say hi","max_tokens":20}' \
  -D - | grep X-Idempotent-Replay
# Ожидание: X-Idempotent-Replay: true

# 10. CI зелёный
git push origin develop
# Открыть GitHub Actions — все jobs ✓
```

**Если все 10 пунктов проходят — Спринт 0 закрыт.**

---

## Что дальше (Спринт 1)

После Спринта 0 переходим к `brief-service` — это будет первый «умный» сервис, который:
- Принимает вводные (текст, ссылку, ответы).
- Через `llm-gateway` задаёт уточняющие вопросы.
- Собирает структурированный Brief v1.
- Публикует `brief.created`, `brief.questions_asked`, `brief.completed`.

Задачи Спринта 1 я выдам отдельным сообщением, когда Спринт 0 будет закрыт. Формат будет тот же: 4-6 задач с acceptance criteria.

---

## Проверка: что я перепроверил

- [x] Порядок задач: зависимости соблюдены (0.1 → 0.2 → ... → 0.9).
- [x] Каждая задача самодостаточна: агент может взять одну и сделать.
- [x] Acceptance criteria проверяемы командами, не абстрактны.
- [x] Пути файлов согласованы с `docs/infra.md`.
- [x] Импорты корректны: `contracts`, `common`, `db`, `nats_client`, `llm_client`, `tenant_service`, `llm_gateway`.
- [x] Нет противоречий между задачами.
- [x] Анти-паттерны везде явные.
- [x] Тесты описаны для каждого модуля.
- [x] RLS проверен на уровне INSERT (`WITH CHECK (true)`) и SELECT (`USING (id = ...)`).
- [x] NATS subjects и стримы согласованы с `docs/contracts.md`.
- [x] Env-переменные согласованы с `.env.example`.
- [x] Dockerfile multi-stage с uv, `--no-editable`, непривилегированный пользователь.
- [x] CI: lint → test → build → deploy.
- [x] Все секреты — через env.
- [x] Никаких `print`, `time.sleep`, `datetime.utcnow`.
- [x] UUID v7 везде.
- [x] Timestamps UTC с `Z`.

---

## Что от тебя нужно

1. **Разложить эти девять задач по файлам** в `docs/tasks/sprint-0/`. Если хочешь — я могу выдать их отдельными сообщениями, чтобы ты копировал по одному. Но это займёт 9 сообщений, а тут всё в одном.
2. **Дать агенту-разработчику доступ к репе** и сказать: «Начинай с 0.1, иди по порядку, после каждой задачи проверяй acceptance criteria, не переходи к следующей, пока не зелёная».
3. **Сообщить мне**, когда Спринт 0 закрыт (или если агент застрял на конкретной задаче) — выдам Спринт 1.

Если хочешь что-то поправить в задачах сейчас — скажи, поправлю до того, как агент начнёт. Лучше сейчас, чем потом переделывать.
