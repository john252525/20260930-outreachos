# Спринт 2B — `icp-service`

Проверил: зависимости от Спринта 0, 1, 2A соблюдены, контракт ICP v1 из `docs/contracts.md` раздел 2 полностью покрыт, порядок задач логичен, acceptance criteria проверяемы. Каждая задача самодостаточна.

## Что такое `icp-service` и почему он изолирован

Это **чистый LLM-сервис без внешнего мира**. Вход — Brief (по id), выход — ICP с сегментами. Никаких HTTP-запросов к сайтам, никаких реестров, никакой OSINT. Только LLM + БД.

**Ключевые принципы:**
1. **Изоляция.** Не знает про sourcing. Публикует `icp.generated` — и всё.
2. **Версионирование.** Каждый ре-генерейт ICP — новая версия. Старые сохраняются.
3. **Валидация весов.** `scoring_weights` сегмента должны суммироваться в 1.0. Если LLM ошибся — перегенерируем или нормализуем.
4. **Опора на Brief.** Не выдумывает, а извлекает из Brief. Если данных нет — фиксирует `low` confidence.
5. **Анти-ICP обязателен.** Кого НЕ трогаем — так же важно, как кого трогаем.

## Архитектура сервиса

```
                    ┌──────────────────────────────────────┐
                    │            icp-service               │
                    │                                       │
   HTTP requests ──►│  API layer (routes)                   │
                    │       │                               │
                    │       ▼                               │
                    │  ICPService (бизнес-логика)           │
                    │       │                               │
                    │       ├──► ICPRepository              │
                    │       ├──► BriefFetcher ──────────────┼──► brief-service (HTTP)
                    │       ├──► ICPGenerator ──────────────┼──► llm-gateway
                    │       ├──► WeightNormalizer (pure)    │
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - icp.generated                     │
                    │   - icp.revised                       │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                                   Postgres
```

**Что НЕ делает:**
- Не ищет компании и контакты.
- Не генерирует письма.
- Не вызывает внешние API, кроме `brief-service` и `llm-gateway`.
- Не имеет UI.

**Модель данных:** таблица `icps`. Один Brief → много ICP (разные версии). `version` — целое, инкрементится.

---

# Задача 2B.1 — Каркас `icp-service` + модель ICP

**Файл:** `docs/tasks/sprint-2b/2b.1-bootstrap.md`

## Цель

Создать каркас сервиса по образцу `brief-service`, определить SQLAlchemy-модель `ICP`, сделать миграцию с RLS. Сервис поднимается, healthcheck зелёный.

## Зависимости

Спринт 0, 1, 2A закрыты.

## Что создать

```
services/icp-service/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_icps.py
├── src/icp_service/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── weight_normalizer.py
│   ├── events.py
│   ├── brief_client.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                 # обёртка над llm-gateway (можно переиспользовать из brief)
│   │   ├── json_utils.py             # переиспользовать
│   │   ├── schemas.py                # схемы ответа LLM
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── generate_icp.py
│   └── api/
│       ├── __init__.py
│       ├── routes.py
│       └── deps.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_weight_normalizer.py
    ├── test_api.py
    └── test_e2e.py
```

## Детали реализации

### `pyproject.toml`

```toml
[project]
name = "icp-service"
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
packages = ["src/icp_service"]
```

### `config.py`

```python
from pydantic import Field

from common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = Field("icp-service", alias="SERVICE_NAME")
    brief_service_url: str = Field(..., alias="BRIEF_SERVICE_URL")
    llm_gateway_url: str = Field(..., alias="LLM_GATEWAY_URL")

    # LLM
    llm_model: str = Field("deepseek-chat", alias="ICP_LLM_MODEL")
    llm_temperature: float = Field(0.4, alias="ICP_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(8192, alias="ICP_LLM_MAX_TOKENS")

    # Валидация
    min_segments: int = Field(1, alias="ICP_MIN_SEGMENTS")
    max_segments: int = Field(5, alias="ICP_MAX_SEGMENTS")
    min_confidence: float = Field(0.6, alias="ICP_MIN_CONFIDENCE")
```

**`llm_max_tokens` = 8192** — ICP больше по объёму, чем Brief. DeepSeek поддерживает.

### `models.py`

```python
from sqlalchemy import Float, ForeignKey, Integer, String
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


class ICP(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "icps"

    brief_id: Mapped[str] = mapped_column(
        # Храним как UUID, но без FK (brief в другом сервисе)
        String(36),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(
        # активная версия для брифа — последняя
        nullable=False,
        default=True,
        index=True,
    )

    # Полный ICP как JSONB (соответствует contracts.ICP)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Денормализованные для поиска
    segments_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        # Один (tenant, brief, version) — уникален
        # но это гарантируется на уровне сервиса, не БД (race редко)
        # Index по (tenant_id, brief_id, version)
    )
```

**Важно:** `brief_id` — без FK, потому что Brief живёт в другом сервисе (`brief-service`). Возможна рассинхронизация — учтём это в `service.py` (проверка существования Brief через HTTP).

### `migrations/versions/0001_create_icps.py`

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_create_icps"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "icps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brief_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("segments_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("llm_confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_icps_tenant_brief", "icps", ["tenant_id", "brief_id"])
    op.create_index("ix_icps_tenant_brief_version", "icps", ["tenant_id", "brief_id", "version"], unique=True)
    op.create_index("ix_icps_tenant_active", "icps", ["tenant_id", "is_active"])
    op.create_index("ix_icps_tenant_created", "icps", ["tenant_id", "created_at"])
    op.execute("CREATE INDEX ix_icps_payload_gin ON icps USING gin (payload jsonb_path_ops)")

    op.execute("ALTER TABLE icps ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY icps_tenant_isolation ON icps
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS icps_tenant_isolation ON icps")
    op.drop_index("ix_icps_payload_gin")
    op.drop_index("ix_icps_tenant_created")
    op.drop_index("ix_icps_tenant_active")
    op.drop_index("ix_icps_tenant_brief_version")
    op.drop_index("ix_icps_tenant_brief")
    op.drop_table("icps")
```

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  icp-service:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/icp-service/Dockerfile
    container_name: outreach-icp-service
    environment:
      <<: *common-env
      SERVICE_NAME: icp-service
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/4
      BRIEF_SERVICE_URL: http://brief-service:8000
      LLM_GATEWAY_URL: http://llm-gateway:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
      brief-service:
        condition: service_started
      llm-gateway:
        condition: service_started
    labels:
      caddy: icp.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

### Обновить `scripts/migrate.sh`

Добавить `icp-service` в `SERVICES_WITH_DB`.

### `Dockerfile`

Скопировать из `brief-service/Dockerfile`, поменять `--package icp-service` и `CMD`.

### `main.py`

По образцу `brief-service.main`. Отличия:
- Свой `Settings`.
- `LLMClient` + `BriefClient`.
- Роутер `icps`.

### `api/routes.py` (пустой пока)

```python
from fastapi import APIRouter


router = APIRouter(prefix="/icps", tags=["icps"])
```

## Acceptance criteria

```bash
# 1. Миграция применяется
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm icp-service alembic upgrade head
# Ожидание: Applying 0001_create_icps... OK

# 2. Сервис поднимается
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d icp-service
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev logs --tail=20 icp-service
# Ожидание: service_started

# 3. Healthcheck
curl -fsS https://icp.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"}

# 4. Таблица + RLS
bash scripts/psql.sh -c "\d+ icps"
# Ожидание: таблица есть, RLS enabled

# 5. OpenAPI
curl -fsS https://icp.dev.aitler.ru/openapi.json | jq .info.title
# Ожидание: "ICP Service"
```

## Подсказки

- **`brief_id` как String(36), не UUID** — потому что brief живёт в другом сервисе, и мы не хотим создавать FK через сервисные границы. Валидация UUID — на уровне Pydantic-схемы.
- **`is_active`** — флаг «текущая версия для брифа». При создании новой версии — старые переводятся в `is_active=False`.
- **`payload` JSONB** — полностью соответствует `contracts.ICP`. Денормализация — только `segments_count` и `llm_confidence` для быстрых запросов.

## Анти-паттерны

- ❌ Не делать FK на `briefs` — это разные сервисы.
- ❌ Не хранить ICP разложенным на колонки — структура сложная, JSONB + валидация через контракт.
- ❌ Не забывать `is_active` — без него невозможно «откатиться» на предыдущую версию.

---

# Задача 2B.2 — WeightNormalizer (валидация и нормализация весов)

**Файл:** `docs/tasks/sprint-2b/2b.2-weights.md`

## Цель

Реализовать детерминированную нормализацию `scoring_weights` сегмента к сумме 1.0. LLM часто ошибается — надо чинить, а не падать.

## Зависимости

2B.1.

## Что создать

```
services/icp-service/src/icp_service/
└── weight_normalizer.py

services/icp-service/tests/
└── test_weight_normalizer.py
```

## Детали реализации

### `weight_normalizer.py`

```python
from typing import Final


REQUIRED_KEYS: Final[frozenset[str]] = frozenset({
    "industry_match",
    "size_match",
    "geo_match",
    "pain_match",
    "trigger_match",
    "role_match",
})


def normalize_weights(weights: dict[str, float] | None) -> tuple[dict[str, float], list[str]]:
    """Нормализует веса к сумме 1.0.

    Правила:
    1. Если ключей нет — возвращаем дефолт (равномерно).
    2. Если есть лишние ключи — отбрасываем.
    3. Если пропущены обязательные — добавляем с весом 0.
    4. Если все нули — равномерное распределение.
    5. Если отрицательные — зажимаем в 0.
    6. Нормализуем к сумме 1.0.

    Возвращает (weights, warnings).
    """
    warnings: list[str] = []
    incoming = dict(weights or {})

    # Отбрасываем лишние ключи
    extra = set(incoming) - REQUIRED_KEYS
    if extra:
        warnings.append(f"extra keys dropped: {sorted(extra)}")
    incoming = {k: v for k, v in incoming.items() if k in REQUIRED_KEYS}

    # Зажимаем отрицательные
    negatives = [k for k, v in incoming.items() if v is not None and v < 0]
    if negatives:
        warnings.append(f"negative weights clamped to 0: {sorted(negatives)}")
    incoming = {k: max(0.0, float(v)) if v is not None else 0.0 for k, v in incoming.items()}

    # Дополняем отсутствующие нулями
    missing = REQUIRED_KEYS - set(incoming)
    if missing:
        warnings.append(f"missing keys filled with 0: {sorted(missing)}")
        for k in missing:
            incoming[k] = 0.0

    # Если сумма нулевая — равномерно
    total = sum(incoming.values())
    if total <= 0:
        warnings.append("all weights zero, using uniform distribution")
        n = len(REQUIRED_KEYS)
        return {k: round(1.0 / n, 6) for k in sorted(REQUIRED_KEYS)}, warnings

    # Нормализуем
    normalized = {k: round(v / total, 6) for k, v in incoming.items()}

    # Компенсация округления: гарантируем, что сумма ровно 1.0
    diff = round(1.0 - sum(normalized.values()), 6)
    if abs(diff) > 0:
        # Добавляем к ключу с максимальным весом
        max_key = max(normalized, key=normalized.get)
        normalized[max_key] = round(normalized[max_key] + diff, 6)

    return normalized, warnings


def is_valid(weights: dict[str, float]) -> bool:
    """Проверяет, что веса валидны (все ключи, сумма = 1.0, нет отрицательных)."""
    if set(weights.keys()) != REQUIRED_KEYS:
        return False
    if any(v < 0 for v in weights.values()):
        return False
    return abs(sum(weights.values()) - 1.0) < 1e-6
```

### Тесты

```python
import pytest
from icp_service.weight_normalizer import normalize_weights, is_valid, REQUIRED_KEYS


def test_normalize_full_valid():
    w = {
        "industry_match": 0.25, "size_match": 0.15, "geo_match": 0.10,
        "pain_match": 0.20, "trigger_match": 0.20, "role_match": 0.10,
    }
    result, warnings = normalize_weights(w)
    assert warnings == []
    assert is_valid(result)


def test_normalize_all_zero():
    result, warnings = normalize_weights({k: 0.0 for k in REQUIRED_KEYS})
    assert "all weights zero" in " ".join(warnings)
    assert is_valid(result)
    assert all(v == pytest.approx(1/6, abs=1e-6) for v in result.values())


def test_normalize_empty():
    result, warnings = normalize_weights(None)
    assert is_valid(result)


def test_normalize_negative():
    w = {"industry_match": -0.5, "size_match": 0.5, "geo_match": 0.5, "pain_match": 0.5, "trigger_match": 0.5, "role_match": 0.5}
    result, warnings = normalize_weights(w)
    assert any("negative" in w for w in warnings)
    assert is_valid(result)


def test_normalize_extra_keys():
    w = {"industry_match": 0.5, "size_match": 0.5, "geo_match": 0.5, "pain_match": 0.5, "trigger_match": 0.5, "role_match": 0.5, "junk": 1.0}
    result, warnings = normalize_weights(w)
    assert any("extra keys" in w for w in warnings)
    assert "junk" not in result
    assert is_valid(result)


def test_normalize_missing_keys():
    w = {"industry_match": 0.5, "size_match": 0.5}
    result, warnings = normalize_weights(w)
    assert any("missing keys" in w for w in warnings)
    assert is_valid(result)


def test_normalize_rounding():
    # 1/3 каждый — сумма может не сойтись до 1.0
    w = {k: 1.0 for k in REQUIRED_KEYS}
    result, _ = normalize_weights(w)
    assert abs(sum(result.values()) - 1.0) < 1e-6
```

## Acceptance criteria

```bash
uv run pytest services/icp-service/tests/test_weight_normalizer.py -v --cov=icp_service.weight_normalizer --cov-report=term-missing
# Ожидание: coverage 100%, все passed

uv run mypy services/icp-service
uv run ruff check services/icp-service
```

## Подсказки

- **Округление до 6 знаков** — баланс между точностью и читаемостью JSON.
- **Компенсация округления** — обязательна, иначе `sum != 1.0` и `is_valid` упадёт.
- **Warnings возвращаются** — потом логируются в `service.py` для отладки промптов.

## Анти-паттерны

- ❌ Не падать на плохих весах — нормализовать и продолжать.
- ❌ Не забывать компенсацию округления.
- ❌ Не терять warnings — они нужны для отладки.

---

# Задача 2B.3 — `BriefClient` и LLM-промпт «Brief → ICP»

**Файл:** `docs/tasks/sprint-2b/2b.3-brief-client-llm.md`

## Цель

Реализовать HTTP-клиент к `brief-service` и промпт для генерации ICP из Brief. Плюс LLM-схемы.

## Зависимости

2B.1, 2B.2.

## Что создать

```
services/icp-service/src/icp_service/
├── brief_client.py
└── llm/
    ├── __init__.py
    ├── client.py                 # копия из brief-service (или переиспользовать)
    ├── json_utils.py             # копия
    ├── schemas.py
    └── prompts/
        ├── __init__.py
        └── generate_icp.py

services/icp-service/tests/
└── test_brief_client.py
```

## Детали реализации

### `brief_client.py`

```python
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from common.errors import AppError


logger = structlog.get_logger()


class BriefNotFoundError(AppError):
    code = "brief_not_found"
    status_code = 404
    message = "Brief not found"


class BriefClient:
    """HTTP-клиент к brief-service."""

    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def get_brief(self, brief_id: str, *, tenant_id: str, trace_id: str = "") -> dict:
        resp = await self._client.get(
            f"/briefs/{brief_id}",
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
            },
        )
        if resp.status_code == 404:
            raise BriefNotFoundError(f"Brief {brief_id} not found")
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
```

**Важно:** клиент **не** использует Idempotency-Key, потому что GET. Retry — на транспортные ошибки и 5xx.

### `llm/schemas.py`

Pydantic-модели для валидации ответа LLM. Должны точно соответствовать `contracts.ICP`.

```python
from pydantic import BaseModel, ConfigDict, Field


class _AntiICP(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = ""
    exclude_industries: list[str] = Field(default_factory=list)
    exclude_company_sizes: list[str] = Field(default_factory=list)
    exclude_geos: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class _Firmographic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    industries: list[str] = Field(default_factory=list)
    sub_industries: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    revenue_range: dict | None = None
    geos: list[str] = Field(default_factory=list)
    company_types: list[str] = Field(default_factory=list)


class _Technographic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    uses_technologies: list[str] = Field(default_factory=list)
    does_not_use_technologies: list[str] = Field(default_factory=list)


class _PainHypothesis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pain: str
    why_relevant: str = ""
    how_we_solve: str = ""
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class _TriggerEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    trigger: str
    detection_hint: str = ""
    weight: float = Field(0.5, ge=0.0, le=1.0)


class _RoleToContact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role_title: str
    role_category: str = "unknown"
    priority: str = "medium"
    why: str = ""


class _ScoringWeights(BaseModel):
    model_config = ConfigDict(extra="ignore")
    industry_match: float = 0.0
    size_match: float = 0.0
    geo_match: float = 0.0
    pain_match: float = 0.0
    trigger_match: float = 0.0
    role_match: float = 0.0


class _Segment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: str = ""
    priority: str = "medium"
    estimated_size: int | None = None
    firmographic: _Firmographic = Field(default_factory=_Firmographic)
    technographic: _Technographic = Field(default_factory=_Technographic)
    pain_hypotheses: list[_PainHypothesis] = Field(default_factory=list)
    trigger_events: list[_TriggerEvent] = Field(default_factory=list)
    roles_to_contact: list[_RoleToContact] = Field(default_factory=list)
    scoring_weights: _ScoringWeights = Field(default_factory=_ScoringWeights)
    estimated_reply_rate: float | None = None
    notes: str | None = None


class _ICPGenerated(BaseModel):
    model_config = ConfigDict(extra="ignore")
    anti_icp: _AntiICP = Field(default_factory=_AntiICP)
    segments: list[_Segment] = Field(default_factory=list)
    llm_confidence: float = Field(0.5, ge=0.0, le=1.0)
    reasoning: str = ""  # краткое объяснение, не сохраняется в ICP, но полезно для логов
```

**Важно:** `reasoning` — для отладки. Не идёт в `contracts.ICP`.

### `llm/prompts/generate_icp.py`

```python
from icp_service.llm.prompts.base import SYSTEM_COMMON, Prompt  # см. ниже base.py


ICP_SCHEMA = """
{
  "anti_icp": {
    "description": "string (кого НЕ трогаем и почему)",
    "exclude_industries": ["string"],
    "exclude_company_sizes": ["smb" | "mid" | "enterprise"],
    "exclude_geos": ["ISO 3166-1 alpha-2"],
    "exclude_keywords": ["string"]
  },
  "segments": [
    {
      "name": "string (краткое, до 60 символов)",
      "description": "string (1-2 предложения)",
      "priority": "high" | "medium" | "low",
      "estimated_size": integer | null,
      "firmographic": {
        "industries": ["string"],
        "sub_industries": ["string"],
        "company_sizes": ["smb" | "mid" | "enterprise"],
        "employee_count_min": integer | null,
        "employee_count_max": integer | null,
        "revenue_range": {"min": number|null, "max": number|null, "currency": "ISO 4217|null"} | null,
        "geos": ["ISO 3166-1 alpha-2"],
        "company_types": ["manufacturer" | "distributor" | "retailer" | "service" | "agency" | "saas" | "other"]
      },
      "technographic": {
        "uses_technologies": ["string"],
        "does_not_use_technologies": ["string"]
      },
      "pain_hypotheses": [
        {"pain": "string", "why_relevant": "string", "how_we_solve": "string", "confidence": 0.0-1.0}
      ],
      "trigger_events": [
        {"trigger": "string", "detection_hint": "string", "weight": 0.0-1.0}
      ],
      "roles_to_contact": [
        {"role_title": "string", "role_category": "decision_maker|influencer|gatekeeper|champion|unknown", "priority": "high|medium|low", "why": "string"}
      ],
      "scoring_weights": {
        "industry_match": 0.0-1.0,
        "size_match": 0.0-1.0,
        "geo_match": 0.0-1.0,
        "pain_match": 0.0-1.0,
        "trigger_match": 0.0-1.0,
        "role_match": 0.0-1.0
      },
      "estimated_reply_rate": 0.0-1.0 | null,
      "notes": "string | null"
    }
  ],
  "llm_confidence": 0.0-1.0,
  "reasoning": "string (1-3 предложения, почему такие сегменты)"
}
"""


def build_generate_icp_prompt(
    *,
    brief_json: str,
    min_segments: int = 1,
    max_segments: int = 5,
) -> Prompt:
    user = f"""Ты — эксперт по B2B-маркетингу и сегментации рынка.

Есть структурированный Brief проекта:

<brief>
{brief_json}
</brief>

Твоя задача — построить ICP (Ideal Customer Profile) с сегментами для целевого outreach.

Требования:
1. Сгенерируй от {min_segments} до {max_segments} сегментов. Сегменты должны быть различимы (разные отрасли, размеры, боли или гео).
2. Для каждого сегмента заполни:
   - firmographic (кого искать по формальным признакам),
   - technographic (какие технологии используются / НЕ используются),
   - pain_hypotheses (какие боли, почему релевантны, как мы их решаем),
   - trigger_events (события, при которых стоит контактировать — найм, раунд, запуск, новость),
   - roles_to_contact (кого именно искать — должности, категория, приоритет),
   - scoring_weights (веса для скоринга — сумма ОБЯЗАТЕЛЬНО = 1.0).
3. anti_icp — кого НЕ трогаем: конкуренты, госсектор (если нецелевой), компании слишком маленькие/большие, нерелевантные гео.
4. llm_confidence — насколько ты уверен в качестве ICP (0.0–1.0). Если в Brief мало данных — ставь низкий.
5. reasoning — 1-3 предложения: почему именно такие сегменты, на чём основано.

ВАЖНО:
- Опирайся ТОЛЬКО на данные из Brief. Не выдумывай отрасли, которых там нет.
- Если в Brief указано "работаем по РФ", не добавляй сегменты с гео "US".
- Если Brief неполный (completeness_score < 0.7) — снижай llm_confidence и в notes сегмента указывай, каких данных не хватает.
- scoring_weights — сумма ровно 1.0. Если не уверен — распредели равномерно.
- estimated_reply_rate — реалистичная оценка (обычно 0.02–0.15 для холодного outreach).

Верни JSON ровно такой структуры (без markdown, без пояснений):
{ICP_SCHEMA}
"""
    return Prompt(
        system=SYSTEM_COMMON,
        user=user,
        task_type="icp_generate_v1",
    )
```

### `llm/prompts/base.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    task_type: str


SYSTEM_COMMON = """Ты — эксперт по B2B-маркетингу и сегментации рынка.

Правила:
- Отвечай ТОЛЬКО валидным JSON, без markdown-обёрток и пояснений.
- Если данные отсутствуют — используй null или пустой массив, не выдумывай.
- Все строки — на русском языке (если Brief на русском), иначе — на языке Brief.
- Не добавляй поля, которых нет в схеме.
- Будь конкретным и обоснованным.
"""
```

### `llm/client.py` и `llm/json_utils.py`

**Переиспользовать из `brief-service`.** Способы:
1. **Скопировать** файлы (быстро, но дублирование).
2. **Вынести в `libs/llm-client`** как `LLMClient` класс (правильно).

**Решение:** скопировать на 2B, вынести в `libs/llm-client` в Спринте 3 (когда будет третий потребитель — composer). Пока двух потребителей достаточно для копипасты.

**Важно:** в `icp_service/llm/client.py` поменять импорты (`from icp_service.config import Settings`, `from icp_service.llm.json_utils import ...`).

### Тесты

`tests/test_brief_client.py` — с использованием `respx` (mock HTTP):

```python
import pytest
import respx
from httpx import Response

from icp_service.brief_client import BriefClient, BriefNotFoundError


@pytest.mark.asyncio
@respx.mock
async def test_get_brief_success():
    respx.get("http://brief-service:8000/briefs/abc").mock(
        return_value=Response(200, json={"id": "abc", "status": "complete"})
    )
    client = BriefClient("http://brief-service:8000")
    result = await client.get_brief("abc", tenant_id="t1")
    assert result["id"] == "abc"
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_brief_not_found():
    respx.get("http://brief-service:8000/briefs/abc").mock(
        return_value=Response(404)
    )
    client = BriefClient("http://brief-service:8000")
    with pytest.raises(BriefNotFoundError):
        await client.get_brief("abc", tenant_id="t1")
    await client.close()
```

**Добавить `respx` в dev-зависимости.**

## Acceptance criteria

```bash
uv run pytest services/icp-service/tests/test_brief_client.py -v
# Ожидание: все passed

uv run mypy services/icp-service
uv run ruff check services/icp-service

# E2E — реальный вызов brief-service
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev exec -T icp-service python - <<'PY'
import asyncio
from icp_service.config import Settings
from icp_service.brief_client import BriefClient

async def main():
    s = Settings()
    c = BriefClient(s.brief_service_url)
    try:
        brief = await c.get_brief("<real_brief_id>", tenant_id="<tenant>")
        print(brief.get("status"), brief.get("completeness_score"))
    finally:
        await c.close()

asyncio.run(main())
PY
# Ожидание: статус и score реального брифа
```

## Подсказки

- **`task_type="icp_generate_v1"`** — для A/B и аналитики.
- **`reasoning`** — не сохраняется в ICP, но логируется. Если LLM часто ошибается — смотрим на reasoning.
- **`respx`** — стандартный инструмент для мока httpx. Лучше, чем `unittest.mock`.

## Анти-паттерны

- ❌ Не вызывать LLM без `task_type`.
- ❌ Не забывать про `brief_id` в headers при вызове brief-service (X-Tenant-ID).
- ❌ Не игнорировать `BriefNotFoundError` — это 404, не 500.

---

# Задача 2B.4 — `ICPService` + endpoints

**Файл:** `docs/tasks/sprint-2b/2b.4-service-api.md`

## Цель

Реализовать основной сценарий: получить Brief → сгенерировать ICP через LLM → нормализовать веса → сохранить → опубликовать событие. Плюс API endpoints.

## Зависимости

2B.1–2B.3.

## Что создать

- `repository.py` — `ICPRepository`.
- `service.py` — `ICPService`.
- `events.py`.
- `schemas.py` — API-схемы.
- `api/routes.py`.
- `api/deps.py`.
- Обновить `main.py`.
- Тесты.

## Детали

### `repository.py`

```python
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from icp_service.models import ICP


class ICPRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, icp_id: UUID) -> ICP | None:
        return await self._s.get(ICP, icp_id)

    async def list_by_brief(self, tenant_id: UUID, brief_id: str) -> list[ICP]:
        stmt = (
            select(ICP)
            .where(ICP.tenant_id == tenant_id, ICP.brief_id == brief_id)
            .order_by(ICP.version.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def get_active(self, tenant_id: UUID, brief_id: str) -> ICP | None:
        stmt = select(ICP).where(
            ICP.tenant_id == tenant_id,
            ICP.brief_id == brief_id,
            ICP.is_active.is_(True),
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_max_version(self, tenant_id: UUID, brief_id: str) -> int:
        stmt = select(ICP.version).where(
            ICP.tenant_id == tenant_id,
            ICP.brief_id == brief_id,
        ).order_by(ICP.version.desc()).limit(1)
        result = (await self._s.execute(stmt)).scalar_one_or_none()
        return result or 0

    async def deactivate_all(self, tenant_id: UUID, brief_id: str) -> None:
        stmt = (
            update(ICP)
            .where(ICP.tenant_id == tenant_id, ICP.brief_id == brief_id, ICP.is_active.is_(True))
            .values(is_active=False)
        )
        await self._s.execute(stmt)

    async def add(self, icp: ICP) -> ICP:
        self._s.add(icp)
        await self._s.flush()
        return icp

    async def list(
        self,
        *,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ICP]:
        stmt = (
            select(ICP)
            .where(ICP.tenant_id == tenant_id)
            .order_by(ICP.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self._s.execute(stmt)).scalars().all())
```

### `schemas.py`

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ICPGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief_id: str = Field(min_length=1, max_length=36)


class ICPRead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    tenant_id: UUID
    brief_id: str
    version: int
    is_active: bool
    payload: dict
    segments_count: int
    llm_confidence: float
    schema_version: str
    created_at: datetime
    updated_at: datetime


class ICPSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    brief_id: str
    version: int
    is_active: bool
    segments_count: int
    llm_confidence: float
    created_at: datetime
```

### `events.py`

```python
from nats_client.publisher import Publisher
from nats_client.subjects import Subjects
from icp_service.models import ICP


async def emit_icp_generated(publisher: Publisher, icp: ICP, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.ICP_GENERATED,
        tenant_id=icp.tenant_id,
        payload={
            "icp": {
                "id": str(icp.id),
                "brief_id": icp.brief_id,
                "version": icp.version,
                "segments_count": icp.segments_count,
            }
        },
        trace_id=trace_id,
        correlation_id=icp.brief_id if isinstance(icp.brief_id, UUID) else None,
    )


async def emit_icp_revised(publisher: Publisher, icp: ICP, *, trace_id: str) -> None:
    await publisher.publish(
        Subjects.ICP_REVISED,
        tenant_id=icp.tenant_id,
        payload={
            "icp": {
                "id": str(icp.id),
                "brief_id": icp.brief_id,
                "version": icp.version,
                "segments_count": icp.segments_count,
            }
        },
        trace_id=trace_id,
    )
```

**Проблема:** `Subjects.ICP_GENERATED` и `ICP_REVISED` уже есть в `nats_client.subjects` (мы добавляли в Спринте 0). Проверить. Если нет — добавить.

**Проблема с `correlation_id`:** `brief_id` — строка UUID, но `correlation_id` в EventEnvelope — `UUID | None`. Нужно преобразовать:

```python
from uuid import UUID
try:
    correlation_uuid = UUID(icp.brief_id)
except (ValueError, TypeError):
    correlation_uuid = None
```

### `service.py` — `ICPService`

```python
import json
from uuid import UUID

import structlog

from common.errors import AppError, NotFoundError, ValidationError
from icp_service.brief_client import BriefClient, BriefNotFoundError
from icp_service.config import Settings
from icp_service.events import emit_icp_generated, emit_icp_revised
from icp_service.llm.client import LLMClient
from icp_service.llm.prompts.generate_icp import build_generate_icp_prompt
from icp_service.llm.schemas import _ICPGenerated
from icp_service.models import ICP
from icp_service.repository import ICPRepository
from icp_service.weight_normalizer import normalize_weights
from nats_client.publisher import Publisher


logger = structlog.get_logger()


class ICPService:
    def __init__(
        self,
        repo: ICPRepository,
        brief_client: BriefClient,
        llm: LLMClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._brief = brief_client
        self._llm = llm
        self._publisher = publisher
        self._settings = settings

    async def generate(
        self,
        *,
        tenant_id: UUID,
        brief_id: str,
        trace_id: str,
    ) -> ICP:
        # 1. Получаем Brief
        try:
            brief = await self._brief.get_brief(brief_id, tenant_id=str(tenant_id), trace_id=trace_id)
        except BriefNotFoundError:
            raise NotFoundError(f"Brief {brief_id} not found")

        if brief.get("status") == "archived":
            raise ValidationError("Cannot generate ICP for archived brief")

        # 2. Генерируем через LLM
        brief_json = json.dumps({
            "identity": brief.get("identity", {}),
            "offering": brief.get("offering", {}),
            "targeting_hints": brief.get("targeting_hints", {}),
            "outreach_goals": brief.get("outreach_goals", {}),
            "completeness_score": brief.get("completeness_score", 0.0),
        }, ensure_ascii=False, indent=2)

        prompt = build_generate_icp_prompt(
            brief_json=brief_json,
            min_segments=self._settings.min_segments,
            max_segments=self._settings.max_segments,
        )

        generated = await self._llm.complete_json(
            tenant_id=str(tenant_id),
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=_ICPGenerated,
            trace_id=trace_id,
        )

        # 3. Нормализуем веса
        warnings_all: list[str] = []
        segments = []
        for seg in generated.segments:
            w = seg.scoring_weights.model_dump()
            normalized, warnings = normalize_weights(w)
            warnings_all.extend([f"segment[{seg.name}]: {w}" for w in warnings])
            seg_dict = seg.model_dump()
            seg_dict["id"] = str(UUID(int=0))  # placeholder, заполним ниже
            seg_dict["scoring_weights"] = normalized
            segments.append(seg_dict)

        if warnings_all:
            logger.warning("icp_weight_normalization_warnings", warnings=warnings_all, brief_id=brief_id)

        if not segments:
            raise AppError("LLM generated no segments", code="icp_empty", status_code=502)

        # 4. Ограничиваем количество сегментов
        segments = segments[:self._settings.max_segments]

        # 5. Генерируем UUID для сегментов
        from uuid6 import uuid7
        for seg in segments:
            seg["id"] = str(uuid7())

        # 6. Собираем payload ICP
        payload = {
            "anti_icp": generated.anti_icp.model_dump(),
            "segments": segments,
            "generated_by": f"llm:{self._settings.llm_model}",
            "llm_confidence": generated.llm_confidence,
        }

        # 7. Определяем версию и деактивируем старые
        max_version = await self._repo.get_max_version(tenant_id, brief_id)
        new_version = max_version + 1
        await self._repo.deactivate_all(tenant_id, brief_id)

        # 8. Сохраняем
        icp = ICP(
            tenant_id=tenant_id,
            brief_id=brief_id,
            version=new_version,
            is_active=True,
            payload=payload,
            segments_count=len(segments),
            llm_confidence=generated.llm_confidence,
        )
        await self._repo.add(icp)

        # 9. Событие
        if new_version == 1:
            await emit_icp_generated(self._publisher, icp, trace_id=trace_id)
        else:
            await emit_icp_revised(self._publisher, icp, trace_id=trace_id)

        logger.info(
            "icp_generated",
            icp_id=str(icp.id),
            brief_id=brief_id,
            version=new_version,
            segments=len(segments),
            llm_confidence=generated.llm_confidence,
        )
        return icp

    async def get(self, icp_id: UUID) -> ICP:
        icp = await self._repo.get(icp_id)
        if icp is None:
            raise NotFoundError(f"ICP {icp_id} not found")
        return icp

    async def list_by_brief(self, *, tenant_id: UUID, brief_id: str) -> list[ICP]:
        return await self._repo.list_by_brief(tenant_id, brief_id)

    async def get_active(self, *, tenant_id: UUID, brief_id: str) -> ICP | None:
        return await self._repo.get_active(tenant_id, brief_id)

    async def list(self, *, tenant_id: UUID, limit: int, offset: int) -> list[ICP]:
        return await self._repo.list(tenant_id=tenant_id, limit=limit, offset=offset)
```

**Важно:**
- `deactivate_all` вызывается **до** `add` новой версии. Иначе unique constraint на `(tenant_id, brief_id, version)` не сработает (но у нас нет такого constraint, есть только index). Но всё равно правильно: сначала деактивировать, потом добавить.
- **Race condition:** два параллельных `generate` для одного brief. Решение: `SELECT ... FOR UPDATE` или advisory lock. **На 2B не делаем** — редко. Добавим в комментарий `# TODO(race): advisory lock`.
- **`min_segments`/`max_segments`** — из конфига. Если LLM вернул 0 сегментов — ошибка. Если больше max — обрезаем.

### `api/routes.py`

```python
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from icp_service.api.deps import get_service
from icp_service.schemas import ICPGenerateRequest, ICPRead, ICPSummary
from icp_service.service import ICPService


router = APIRouter(prefix="/icps", tags=["icps"])


@router.post("", response_model=ICPRead, status_code=status.HTTP_201_CREATED)
async def generate_icp(
    data: ICPGenerateRequest,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.generate(
        tenant_id=tenant_id,
        brief_id=data.brief_id,
        trace_id=get_trace_id() or "",
    )
    return ICPRead.model_validate(icp, from_attributes=True)


@router.get("/{icp_id}", response_model=ICPRead)
async def get_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    icp = await svc.get(icp_id)
    return ICPRead.model_validate(icp, from_attributes=True)


@router.get("", response_model=list[ICPSummary])
async def list_icps(
    brief_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ICPService = Depends(get_service),
) -> list[ICPSummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")

    if brief_id:
        icps = await svc.list_by_brief(tenant_id=tenant_id, brief_id=brief_id)
    else:
        icps = await svc.list(tenant_id=tenant_id, limit=limit, offset=offset)

    return [
        ICPSummary(
            id=i.id,
            brief_id=i.brief_id,
            version=i.version,
            is_active=i.is_active,
            segments_count=i.segments_count,
            llm_confidence=i.llm_confidence,
            created_at=i.created_at,
        )
        for i in icps
    ]


@router.get("/active/by-brief/{brief_id}", response_model=ICPRead)
async def get_active_icp(
    brief_id: str,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.get_active(tenant_id=tenant_id, brief_id=brief_id)
    if icp is None:
        from common.errors import NotFoundError
        raise NotFoundError(f"No active ICP for brief {brief_id}")
    return ICPRead.model_validate(icp, from_attributes=True)
```

### `api/deps.py`

```python
from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from icp_service.repository import ICPRepository
from icp_service.service import ICPService


async def get_service(request: Request) -> AsyncIterator[ICPService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session:
        async with session.begin():
            if tenant_id is not None:
                await set_tenant_context(session, tenant_id)
            yield ICPService(
                repo=ICPRepository(session),
                brief_client=request.app.state.brief_client,
                llm=request.app.state.llm,
                publisher=request.app.state.publisher,
                settings=request.app.state.settings,
            )
```

### `main.py` (обновить)

```python
from icp_service.brief_client import BriefClient
from icp_service.llm.client import LLMClient

# в lifespan:
app.state.llm = LLMClient(settings)
app.state.brief_client = BriefClient(settings.brief_service_url)
# при shutdown:
await app.state.llm.close()
await app.state.brief_client.close()
```

## Acceptance criteria

```bash
# 1. Создать ICP
ICP=$(curl -sX POST https://icp.dev.aitler.ru/icps \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: icp-gen-1" \
  -d '{"brief_id": "'$BRIEF_ID'"}')
echo $ICP | jq .
# Ожидание: icp с payload.segments[], version: 1, is_active: true

ICP_ID=$(echo $ICP | jq -r .id)

# 2. Получить ICP
curl -s -H "X-Tenant-ID: $TENANT" https://icp.dev.aitler.ru/icps/$ICP_ID | jq '.payload.segments | length'
# Ожидание: >= 1

# 3. Проверить веса
curl -s -H "X-Tenant-ID: $TENANT" https://icp.dev.aitler.ru/icps/$ICP_ID | jq '.payload.segments[0].scoring_weights | to_entries | map(.value) | add'
# Ожидание: 1.0 (или очень близко)

# 4. Повторная генерация — версия 2
curl -sX POST https://icp.dev.aitler.ru/icps \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: icp-gen-2" \
  -d '{"brief_id": "'$BRIEF_ID'"}' | jq '.version, .is_active'
# Ожидание: 2, true

# 5. Версия 1 теперь is_active=false
curl -s -H "X-Tenant-ID: $TENANT" https://icp.dev.aitler.ru/icps/$ICP_ID | jq .is_active
# Ожидание: false

# 6. Active для брифа — версия 2
curl -s -H "X-Tenant-ID: $TENANT" https://icp.dev.aitler.ru/icps/active/by-brief/$BRIEF_ID | jq .version
# Ожидание: 2

# 7. События в NATS
bash scripts/nats-cli.sh stream view BRIEFS --last 30 | grep -E "icp\.(generated|revised)"
# Ожидание: оба типа

# 8. LLM call записан
bash scripts/psql.sh -c "SELECT task_type, count(*) FROM llm_calls WHERE tenant_id='$TENANT' AND task_type LIKE 'icp%' GROUP BY task_type;"
# Ожидание: icp_generate_v1, >= 2
```

## Подсказки

- **`deactivate_all` + `add`** — в одной транзакции через `session_scope`. Не коммитить между ними.
- **Race condition** — реально бывает редко. TODO на будущее.
- **`brief_id` валидация** — Pydantic-схема проверяет length, но не UUID-формат. Можно добавить pattern. Пока length достаточно.
- **`llm_confidence < min_confidence`** — можно логировать как warning, но не падать. Флаг для ревью — в metadata.

## Анти-паттерны

- ❌ Не коммитить между `deactivate_all` и `add`.
- ❌ Не позволять `version` сбиваться — только `max_version + 1`.
- ❌ Не игнорировать warnings из `normalize_weights` — логировать.
- ❌ Не пускать генерацию для `archived` brief.

---

# Задача 2B.5 — Revise и управление версиями

**Файл:** `docs/tasks/sprint-2b/2b.5-revise.md`

## Цель

Добавить эндпоинты:
- `POST /icps/{id}/revise` — перегенерировать ICP (новая версия) на основе того же брифа.
- `POST /icps/{id}/activate` — сделать конкретную версию активной (откат).
- `DELETE /icps/{id}` — soft-delete (деактивировать).

## Зависимости

2B.4.

## Детали

### Методы в `service.py`

```python
async def revise(self, *, tenant_id: UUID, icp_id: UUID, trace_id: str) -> ICP:
    """Перегенерировать ICP — новая версия для того же брифа."""
    icp = await self.get(icp_id)
    # Просто вызываем generate снова
    return await self.generate(
        tenant_id=tenant_id,
        brief_id=icp.brief_id,
        trace_id=trace_id,
    )


async def activate(self, *, tenant_id: UUID, icp_id: UUID, trace_id: str) -> ICP:
    """Сделать конкретную версию активной. Остальные деактивируются."""
    icp = await self.get(icp_id)
    if icp.is_active:
        return icp
    await self._repo.deactivate_all(tenant_id, icp.brief_id)
    icp.is_active = True
    await self._repo._s.flush()
    await emit_icp_revised(self._publisher, icp, trace_id=trace_id)
    return icp


async def deactivate(self, *, tenant_id: UUID, icp_id: UUID, trace_id: str) -> ICP:
    """Деактивировать ICP (не удаляя)."""
    icp = await self.get(icp_id)
    if not icp.is_active:
        return icp
    icp.is_active = False
    await self._repo._s.flush()
    await emit_icp_revised(self._publisher, icp, trace_id=trace_id)
    return icp
```

### Роуты

```python
@router.post("/{icp_id}/revise", response_model=ICPRead, status_code=201)
async def revise_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.revise(tenant_id=tenant_id, icp_id=icp_id, trace_id=get_trace_id() or "")
    return ICPRead.model_validate(icp, from_attributes=True)


@router.post("/{icp_id}/activate", response_model=ICPRead)
async def activate_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.activate(tenant_id=tenant_id, icp_id=icp_id, trace_id=get_trace_id() or "")
    return ICPRead.model_validate(icp, from_attributes=True)


@router.post("/{icp_id}/deactivate", response_model=ICPRead)
async def deactivate_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.deactivate(tenant_id=tenant_id, icp_id=icp_id, trace_id=get_trace_id() or "")
    return ICPRead.model_validate(icp, from_attributes=True)
```

## Acceptance criteria

```bash
# 1. Revise — новая версия
curl -sX POST https://icp.dev.aitler.ru/icps/$ICP_ID/revise \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: revise-1" | jq '.version, .is_active'
# Ожидание: 3 (если было 2), true

# 2. Откат — activate старой версии
curl -sX POST https://icp.dev.aitler.ru/icps/$ICP_ID/activate \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: activate-1" | jq '.version, .is_active'
# Ожидание: 1 (вернулись к v1), true

# 3. Проверить, что v3 теперь не активна
curl -s -H "X-Tenant-ID: $TENANT" https://icp.dev.aitler.ru/icps/active/by-brief/$BRIEF_ID | jq .version
# Ожидание: 1
```

## Подсказки

- **`revise` = `generate`** на тот же brief. Не нужно дублировать логику.
- **`activate`** — старый ICP становится активным, новый (последний) — неактивным. Это позволяет «откатиться» к предыдущей версии.
- **`deactivate`** — может оставить brief без активного ICP. Это OK, потом можно активировать другую версию.

## Анти-паттерны

- ❌ Не удалять ICP физически.
- ❌ Не позволять несколько активных ICP для одного брифа — `deactivate_all` перед активацией.
- ❌ Не забывать события.

---

# Задача 2B.6 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-2b/2b.6-tests.md`

## Цель

Довести покрытие до 90%+, E2E-тест полного цикла (Brief → ICP → revise → activate), обновить CI.

## Зависимости

2B.1–2B.5.

## Что создать

### `tests/conftest.py`

По образцу `brief-service`. Нужны:
- Postgres (test database).
- NATS (testcontainer или mock).
- Fake brief-service (respx).
- Fake llm-gateway (respx).

**Важно:** для E2E без реального brief-service и llm-gateway используем `respx` для мока HTTP.

### `tests/test_e2e.py`

```python
import pytest
import respx
from httpx import Response

from icp_service.main import create_app


@pytest.mark.asyncio
@respx.mock
async def test_full_icp_cycle(client, headers, tenant_id):
    brief_id = "0190f3a2-0000-0000-0000-000000000001"

    # Mock brief-service
    respx.get(f"http://brief-service:8000/briefs/{brief_id}").mock(
        return_value=Response(200, json={
            "id": brief_id,
            "status": "complete",
            "completeness_score": 0.9,
            "identity": {"industry": "Промышленное производство", "geo_primary": ["RU"], "language": "ru", "project_name": "Test"},
            "offering": {"what_we_sell": "Гидроборты", "differentiators": ["Собственное производство"]},
            "targeting_hints": {"role_hints": ["Директор по закупкам"]},
            "outreach_goals": {"primary_goal": "partnership", "tone_of_voice": "technical"},
        })
    )

    # Mock llm-gateway
    respx.post("http://llm-gateway:8000/v1/complete").mock(
        return_value=Response(200, json={
            "text": '''{
                "anti_icp": {"description": "Конкуренты", "exclude_industries": ["Гидроборты"], "exclude_company_sizes": [], "exclude_geos": [], "exclude_keywords": []},
                "segments": [{
                    "name": "Дистрибьюторы ПТО",
                    "description": "Компании, продающие подъёмно-транспортное оборудование",
                    "priority": "high",
                    "firmographic": {"industries": ["Логистика"], "company_sizes": ["mid"], "geos": ["RU"], "company_types": ["distributor"]},
                    "technographic": {},
                    "pain_hypotheses": [{"pain": "Долгие поставки", "why_relevant": "Импортозамещение", "how_we_solve": "Локальное производство", "confidence": 0.8}],
                    "trigger_events": [],
                    "roles_to_contact": [{"role_title": "Директор по закупкам", "role_category": "decision_maker", "priority": "high", "why": "Решает закупки"}],
                    "scoring_weights": {"industry_match": 0.3, "size_match": 0.15, "geo_match": 0.1, "pain_match": 0.2, "trigger_match": 0.15, "role_match": 0.1},
                    "estimated_reply_rate": 0.05,
                    "notes": null
                }],
                "llm_confidence": 0.85,
                "reasoning": "Основано на отрасли и гео"
            }''',
            "model": "deepseek-chat",
            "tokens_in": 1000,
            "tokens_out": 500,
            "cost_usd": 0.001,
            "latency_ms": 3000,
        })
    )

    # 1. Generate
    resp = await client.post("/icps", json={"brief_id": brief_id}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 1
    assert data["is_active"] is True
    assert data["segments_count"] == 1
    icp_id = data["id"]

    # 2. Проверка весов
    weights = data["payload"]["segments"][0]["scoring_weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-6

    # 3. Revise
    resp = await client.post(f"/icps/{icp_id}/revise", headers={**headers, "Idempotency-Key": "rev-1"})
    assert resp.status_code == 201
    assert resp.json()["version"] == 2

    # 4. Активировать v1
    resp = await client.post(f"/icps/{icp_id}/activate", headers={**headers, "Idempotency-Key": "act-1"})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # 5. Active для брифа — v1
    resp = await client.get(f"/icps/active/by-brief/{brief_id}", headers=headers)
    assert resp.json()["version"] == 1

    # 6. RLS: другой тенант
    other = {"X-Tenant-ID": "00000000-0000-0000-0000-000000000099"}
    resp = await client.get(f"/icps/{icp_id}", headers=other)
    assert resp.status_code == 404
```

### Обновить CI

Добавить `icp-service` в matrix build-images.

## Acceptance criteria

```bash
uv run pytest services/icp-service/tests/ -v --cov=icp_service --cov-report=term-missing
# Ожидание: coverage >= 90%

uv run mypy services/icp-service
uv run ruff check services/icp-service

# E2E на dev
# См. выше — все шаги

# CI
git push origin develop
# GitHub Actions — зелёные
```

## Подсказки

- **respx** — единый подход для мока brief-service и llm-gateway.
- **Не вызывать реальный LLM в тестах** — только mock.
- **Testcontainers для Postgres** — или общий testdatabase, сносящийся в fixture.

## Анти-паттерны

- ❌ Не использовать реальный brief-service в E2E — слишком связанно.
- ❌ Не забывать мок llm-gateway.
- ❌ Не тестировать с реальной БД без cleanup.

---

## Финальная E2E-проверка Спринта 2B

```bash
# 0. Setup
export TENANT="<sandbox_id>"
export BASE="https://icp.dev.aitler.ru"

# 1. Создать brief (если нет)
BRIEF=$(curl -sX POST https://brief.dev.aitler.ru/briefs \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-b1" \
  -d '{"text": "Производим гидроборты для грузовиков. Хотим найти дистрибьюторов в РФ."}')
BRIEF_ID=$(echo $BRIEF | jq -r .id)

# 2. Ответить на вопросы, пока не complete
for i in $(seq 0 10); do
  STATUS=$(curl -s -H "X-Tenant-ID: $TENANT" https://brief.dev.aitler.ru/briefs/$BRIEF_ID | jq -r .status)
  [ "$STATUS" = "complete" ] && break
  PENDING=$(curl -s -H "X-Tenant-ID: $TENANT" https://brief.dev.aitler.ru/briefs/$BRIEF_ID | jq '[.qa_history | to_entries[] | select(.value.answered_at == null) | .key][0]')
  [ "$PENDING" = "null" ] && break
  curl -sX POST https://brief.dev.aitler.ru/briefs/$BRIEF_ID/answers \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: $TENANT" \
    -H "Idempotency-Key: e2e-a-$i" \
    -d "{\"question_index\": $PENDING, \"answer\": \"Ответ $i: средний чек 300k, работаем по РФ, ищем дистрибьюторов ПТО.\"}" > /dev/null
done

# 3. Генерировать ICP
ICP=$(curl -sX POST $BASE/icps \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-icp-1" \
  -d '{"brief_id": "'$BRIEF_ID'"}')
ICP_ID=$(echo $ICP | jq -r .id)
echo "ICP: $ICP_ID"
echo $ICP | jq '{version, segments_count, llm_confidence, is_active}'
# Ожидание: version=1, segments_count >= 1

# 4. Проверить веса сегментов
echo $ICP | jq '.payload.segments[] | {name, weights_sum: (.scoring_weights | to_entries | map(.value) | add)}'
# Ожидание: weights_sum = 1.0 для каждого

# 5. Проверить anti_icp
echo $ICP | jq '.payload.anti_icp'
# Ожидание: не пустой

# 6. Revise
curl -sX POST $BASE/icps/$ICP_ID/revise \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-revise" | jq '{version, is_active}'
# Ожидание: version=2, is_active=true

# 7. v1 теперь неактивна
curl -s -H "X-Tenant-ID: $TENANT" $BASE/icps/$ICP_ID | jq .is_active
# Ожидание: false

# 8. Откат к v1
curl -sX POST $BASE/icps/$ICP_ID/activate \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: e2e-activate" | jq '{version, is_active}'
# Ожидание: version=1, is_active=true

# 9. Active для брифа
curl -s -H "X-Tenant-ID: $TENANT" $BASE/icps/active/by-brief/$BRIEF_ID | jq .version
# Ожидание: 1

# 10. События в NATS
bash scripts/nats-cli.sh stream view BRIEFS --last 30 | grep -E "icp\.(generated|revised)"
# Ожидание: оба типа

# 11. LLM calls
bash scripts/psql.sh -c "SELECT task_type, count(*) FROM llm_calls WHERE tenant_id='$TENANT' AND task_type LIKE 'icp%' GROUP BY task_type;"
# Ожидание: icp_generate_v1, >= 2

# 12. RLS
OTHER="00000000-0000-0000-0000-000000000000"
curl -s -H "X-Tenant-ID: $OTHER" $BASE/icps/$ICP_ID -w "\n%{http_code}\n"
# Ожидание: 404

# 13. CI
git push origin develop
# Зелёные
```

**Если все 13 пунктов проходят — Спринт 2B закрыт.**

---

## Проверка: что я перепроверил

- [x] Порядок задач: 2B.1 → 2B.2 → 2B.3 → 2B.4 → 2B.5 → 2B.6, зависимости соблюдены.
- [x] Контракт ICP v1 из `docs/contracts.md` раздел 2 полностью покрыт в `llm/schemas.py`.
- [x] WeightNormalizer — детерминированный, компенсирует ошибки LLM.
- [x] Версионирование: `version` = `max_version + 1`, старые деактивируются.
- [x] `is_active` — ровно один на brief.
- [x] `brief_id` без FK (другой сервис), валидация через HTTP-вызов.
- [x] BriefClient с retry на транспортные ошибки и 5xx.
- [x] `reasoning` — не сохраняется в ICP, только логируется.
- [x] `min_confidence` / `max_segments` / `min_segments` — конфигурируемы.
- [x] События: `icp.generated` (v1), `icp.revised` (v2+ и activate/deactivate).
- [x] RLS на `icps`.
- [x] E2E-тест покрывает весь цикл.
- [x] Mock через respx для brief-service и llm-gateway.
- [x] Mypy strict, ruff, pytest.
- [x] Никаких `print`, `time.sleep`, `datetime.utcnow`.
- [x] Race condition на параллельных `generate` — TODO в комментарии, не блокер.
- [x] `Subjects.ICP_GENERATED` / `ICP_REVISED` — проверить, что есть в `nats_client.subjects`. Если нет — добавить (мы их добавляли в Спринте 0).

---

## Что дальше (Спринт 2C)

После закрытия 2B переходим к **`sourcing-service`** — самому сложному сервису Спринта 2. Коннекторы к источникам (веб-поиск, парсеры, реестры РФ), LLM-нормализатор, скоринг по ICP, оркестрация записи в `contact-store`.

Задачи 2C выдам, когда 2B будет закрыт. Это будет большая выдача — возможно, разобью на под-под-спринты (2C.1 — каркас + 1 коннектор, 2C.2 — остальные коннекторы, 2C.3 — скоринг и оркестрация).

**Что от тебя нужно сейчас:**
1. Разложить эти 6 задач по файлам в `docs/tasks/sprint-2b/`.
2. Дать агенту: «Начинай с 2B.1, иди по порядку, после каждой задачи проверяй acceptance criteria».
3. Сообщить мне, когда 2B закрыт (или если агент застрял).

Если хочешь что-то поправить в задачах сейчас — скажи.