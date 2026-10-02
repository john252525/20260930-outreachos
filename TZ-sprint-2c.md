# Спринт 2C — `sourcing-service`
Проверил: зависимости от Спринта 0, 1, 2A, 2B соблюдены, порядок задач логичен, acceptance criteria 
проверяемы, нет противоречий с `docs/contracts.md`. Учёл, что 2C — самый рискованный спринт (внешние 
API, парсеры, нестабильные источники), поэтому разбил его на **3 под-под-спринта: 2C.1 → 2C.2 → 
2C.3**, чтобы можно было закрывать поэтапно и не блокироваться на одном коннекторе.
## Почему 2C разбит на три части
**2C.1 — каркас + первый коннектор (веб-поиск).** Поднимаем сервис, делаем архитектуру коннекторов, 
реализуем один простой источник (Serper/Yandex XML), доводим до E2E: «запустил поиск → получил сырые 
результаты → нормализовал через LLM → записал в contact-store». Это критично: если архитектура 
коннекторов окажется неудачной, переделать её с одним коннектором дешево, с пятью — больно. **2C.2 — 
остальные коннекторы.** Парсеры сайтов (Playwright), реестры РФ (Rusprofile/ЕГРЮЛ), плюс 
опциональный обогатитель email/phone. Каждый коннектор — отдельная задача, можно параллелить. **2C.3 
— скоринг + оркестрация + аналитика поисков.** Scoring по ICP, дедуп результатов, прогресс/отмена, 
метрики. **Зарубежные источники (Crunchbase, LinkedIn) — НЕ в этом спринте.** Отдельный спринт 2D, 
когда РФ-направление заработает. Причины: LinkedIn банит, Crunchbase платный, и там другая специфика 
нормализации. **Fuzzy-match компаний через LLM — НЕ в этом спринте.** Сначала детерминированный 
дедуп в contact-store, посмотрим на реальных данных, нужен ли fuzzy.
## Что такое `sourcing-service` и его архитектура
Это **оркестратор OSINT**. Он не хранит данные (это делает contact-store), не определяет ICP (это 
делает icp-service). Он: 1. Читает ICP (по `icp_id` и `segment_id`). 2. Определяет, какие источники 
использовать. 3. Дёргает коннекторы параллельно/последовательно. 4. Нормализует сырые результаты 
через LLM. 5. Скорит по ICP. 6. Записывает в contact-store. 7. Публикует события. ```
                    ┌────────────────────────────────────────────┐ │ sourcing-service │ │ │ HTTP 
   POST ──────►│ API: POST /searches │ /searches │ │ │
                    │ ▼ │ │ SearchOrchestrator │ │ │ │ │ ├──► ICPClient ──────────────────────┼──► 
                    icp-service │ ├──► ContactStoreClient ─────────────┼──► contact-store │ ├──► 
                    LLMClient ──────────────────────┼──► llm-gateway │ │ │ │ ├──► ConnectorRegistry 
                    │ │ │ │ │ │ │ ├──► WebSearchConnector ─────┼──► Serper / Yandex XML │ │ ├──► 
                    WebsiteParserConnector ─┼──► Playwright + сайты │ │ ├──► RegistryConnector 
                    ──────┼──► Rusprofile / ЕГРЮЛ │ │ └──► EnricherConnector ──────┼──► Hunter / 
                    Snov │ │ │ │ ├──► Normalizer (LLM) │ │ ├──► Scorer (pure + LLM hints) │ │ └──► 
                    Persister (contact-store) │ │ │ │ Events: │ │ - contacts.search_started │ │ - 
                    contacts.found │ │ - contacts.enriched │ 
                    └────────────────────────────────────────────┘
``` **Ключевые концепции:** 1. **Connector** — абстракция над источником. Вход: критерии поиска (из 
ICP-сегмента). Выход: список `RawCandidate` — сырых результатов (URL, сниппет, заголовок, 
метаданные). Коннектор **не** нормализует, **не** скорит, **не** пишет в БД. Только достаёт. 2. 
**Normalizer** — превращает `RawCandidate` в структурированный `Company`/`Contact` через LLM. Каждый 
кандидат — отдельный LLM-вызов (или батч). Evidence сохраняется. 3. **Scorer** — оценивает 
соответствие ICP. Считает по `scoring_weights` сегмента. Отсекает тех, у кого score ниже порога. 4. 
**Persister** — отправляет в contact-store через bulk upsert. Дедуп там. 5. **SearchJob** — единица 
работы. Хранится в БД. Имеет статус (pending/running/completed/failed/cancelled), прогресс, 
результаты (id созданных компаний/контактов). **Ограничения (важно):** - **Лимит источников на 
поиск** — не дёргать все сразу. Настраиваемо. - **Rate limit** на каждый коннектор. Serper — N 
запросов/сек, Yandex XML — M запросов/день, Playwright — не больше K параллельных браузеров. - 
**Дедуп на уровне sourcing** — если два коннектора вернули один и тот же URL/домен, обрабатываем 
один раз. - **Cost tracking** — каждый внешний вызов и LLM-вызов учитывается. Sourcing может быстро 
сжечь бюджет, если не следить. ---
# 2C.1 — Каркас + WebSearchConnector
---
# Задача 2C.1.1 — Каркас `sourcing-service` + модели
**Файл:** `docs/tasks/sprint-2c/2c.1.1-bootstrap.md`
## Цель
Создать каркас сервиса по образцу `icp-service`, определить SQLAlchemy-модели `SearchJob` и 
`SearchJobItem`, сделать миграцию с RLS. Сервис поднимается, healthcheck зелёный.
## Зависимости
Спринт 2A, 2B закрыты.
## Что создать
``` services/sourcing-service/ ├── pyproject.toml ├── Dockerfile ├── alembic.ini ├── migrations/ │ 
├── env.py │ ├── script.py.mako │ └── versions/ │ └── 0001_create_search_jobs.py ├── 
src/sourcing_service/ │ ├── __init__.py │ ├── main.py │ ├── config.py │ ├── models.py │ ├── 
schemas.py │ ├── repository.py │ ├── service.py │ ├── events.py │ ├── clients/ │ │ ├── __init__.py │ 
│ ├── icp_client.py │ │ └── contact_store_client.py │ ├── connectors/ │ │ ├── __init__.py │ │ ├── 
base.py │ │ └── registry.py │ ├── llm/ │ │ ├── __init__.py │ │ ├── client.py # копия │ │ ├── 
json_utils.py # копия │ │ ├── schemas.py │ │ └── prompts/ │ │ ├── __init__.py │ │ └── 
normalize_candidate.py │ ├── scoring/ │ │ ├── __init__.py │ │ └── scorer.py │ └── api/ │ ├── 
__init__.py │ ├── routes.py │ └── deps.py └── tests/
    ├── __init__.py ├── conftest.py └── test_api.py ```
## Детали реализации
### `pyproject.toml`
```toml [project] name = "sourcing-service" version = "0.1.0" requires-python = ">=3.12" 
dependencies = [
    "fastapi>=0.115", "uvicorn[standard]>=0.32", "pydantic>=2.9", "pydantic-settings>=2.6", 
    "sqlalchemy[asyncio]>=2.0.36", "asyncpg>=0.30", "alembic>=1.14", "redis>=5.2", "httpx>=0.27", 
    "structlog>=24.4", "tenacity>=9.0", "python-stdnum>=1.20", "tldextract>=5.1", # для извлечения 
    домена из URL "common", "contracts", "db", "nats-client", "llm-client",
] [build-system] requires = ["hatchling"] build-backend = "hatchling.build" 
[tool.hatch.build.targets.wheel] packages = ["src/sourcing_service"] ``` **Пока без Playwright и 
bs4** — они понадобятся в 2C.2. В 2C.1 достаточно httpx.
### `config.py`
```python from pydantic import Field from common.config import BaseServiceSettings class 
Settings(BaseServiceSettings):
    service_name: str = Field("sourcing-service", alias="SERVICE_NAME") icp_service_url: str = 
    Field(..., alias="ICP_SERVICE_URL") contact_store_url: str = Field(..., 
    alias="CONTACT_STORE_URL") llm_gateway_url: str = Field(..., alias="LLM_GATEWAY_URL")
    # Serper (Google Search API)
    serper_api_key: str = Field("", alias="SERPER_API_KEY") serper_base_url: str = 
    Field("https://google.serper.dev", alias="SERPER_BASE_URL") serper_rate_limit_per_sec: float = 
    Field(5.0, alias="SERPER_RATE_LIMIT_PER_SEC")
    # Yandex XML (поиск)
    yandex_xml_user: str = Field("", alias="YANDEX_XML_USER") yandex_xml_key: str = Field("", 
    alias="YANDEX_XML_KEY") yandex_xml_rate_limit_per_day: int = Field(1000, 
    alias="YANDEX_XML_RATE_LIMIT_PER_DAY")
    # LLM
    llm_model: str = Field("deepseek-chat", alias="SOURCING_LLM_MODEL") llm_temperature: float = 
    Field(0.2, alias="SOURCING_LLM_TEMPERATURE") llm_max_tokens: int = Field(4096, 
    alias="SOURCING_LLM_MAX_TOKENS")
    # Sourcing limits
    max_candidates_per_source: int = Field(50, alias="SOURCING_MAX_CANDIDATES_PER_SOURCE") 
    max_sources_per_search: int = Field(5, alias="SOURCING_MAX_SOURCES_PER_SEARCH") 
    min_score_threshold: float = Field(0.5, alias="SOURCING_MIN_SCORE")
    # Concurrency
    max_parallel_sources: int = Field(3, alias="SOURCING_MAX_PARALLEL_SOURCES") max_parallel_llm: 
    int = Field(5, alias="SOURCING_MAX_PARALLEL_LLM")
```
### `models.py`
Две таблицы: `search_jobs` (задача) и `search_job_items` (найденные кандидаты, для аналитики и 
retry). ```python from datetime import datetime from uuid import UUID from sqlalchemy import 
Boolean, DateTime, Float, ForeignKey, Integer, String, Text from sqlalchemy.dialects.postgresql 
import JSONB from sqlalchemy.orm import Mapped, mapped_column, relationship from db.base import Base 
from db.mixins import (
    MetadataMixin, SchemaVersionMixin, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin, ) class 
SearchJob(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, 
MetadataMixin):
    __tablename__ = "search_jobs" icp_id: Mapped[UUID] = mapped_column(nullable=False, index=True) 
    segment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True) brief_id: 
    Mapped[str] = mapped_column(String(36), nullable=False, index=True) status: Mapped[str] = 
    mapped_column(
        String(32), nullable=False, default="pending", index=True ) # pending | running | completed 
    | failed | cancelled
    # Параметры поиска
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {sources: [...], limit_per_source: 50, geo: "RU", language: "ru"} Прогресс
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {stage: "sourcing" | "normalizing" | "scoring" | "persisting", sources_done: 2, sources_total: 
    #  3, candidates_raw: 120, candidates_normalized: 80, candidates_persisted: 45}
    # Результаты
    candidates_raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0) 
    candidates_normalized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0) 
    candidates_persisted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0) 
    companies_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0) 
    companies_merged: Mapped[int] = mapped_column(Integer, nullable=False, default=0) 
    contacts_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0) 
    contacts_merged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Метрики
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0) duration_ms: 
    Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ошибки
    error: Mapped[str | None] = mapped_column(Text, nullable=True) error_stage: Mapped[str | None] = 
    mapped_column(String(32), nullable=True) started_at: Mapped[datetime | None] = 
    mapped_column(DateTime(timezone=True), nullable=True) finished_at: Mapped[datetime | None] = 
    mapped_column(DateTime(timezone=True), nullable=True) trace_id: Mapped[str | None] = 
    mapped_column(String(64), nullable=True) items: Mapped[list["SearchJobItem"]] = 
    relationship(back_populates="job", cascade="all, delete-orphan")
class SearchJobItem(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin): """Отдельный найденный 
    кандидат. Для аналитики и retry.""" __tablename__ = "search_job_items" job_id: Mapped[UUID] = 
    mapped_column(ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False, index=True) 
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True) # "serper" | 
    "yandex_xml" | ... source_url: Mapped[str | None] = mapped_column(Text, nullable=True) 
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # После нормализации
    normalized_company: Mapped[dict | None] = mapped_column(JSONB, nullable=True) 
    normalized_contacts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Скоринг
    score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True) score_breakdown: 
    Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Результат
    status: Mapped[str] = mapped_column( String(32), nullable=False, default="raw", index=True ) # 
    raw | normalized | scored | persisted | skipped | failed skip_reason: Mapped[str | None] = 
    mapped_column(String(128), nullable=True) error: Mapped[str | None] = mapped_column(Text, 
    nullable=True) company_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True) 
    contact_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True) job: Mapped[SearchJob] = 
    relationship(back_populates="items")
``` **Важно:** - `SearchJob` хранит агрегаты (counts, cost, duration). `SearchJobItem` хранит каждый 
кандидат. - `segment_id` как String — потому что это UUID из ICP payload, но не FK. - `progress` — 
для live-статуса. Обновляется на каждом этапе. - `company_id` / `contact_ids` — результат persist в 
contact-store. Для отслеживания «что этот поиск создал».
### Миграция
```python def upgrade() -> None: op.create_table( "search_jobs", sa.Column("id", 
        postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("tenant_id", 
        postgresql.UUID(as_uuid=True), nullable=False), sa.Column("icp_id", 
        postgresql.UUID(as_uuid=True), nullable=False), sa.Column("segment_id", sa.String(36), 
        nullable=False), sa.Column("brief_id", sa.String(36), nullable=False), sa.Column("status", 
        sa.String(32), nullable=False, server_default="pending"), sa.Column("params", 
        postgresql.JSONB, nullable=False, server_default="{}"), sa.Column("progress", 
        postgresql.JSONB, nullable=False, server_default="{}"), sa.Column("candidates_raw_count", 
        sa.Integer, nullable=False, server_default="0"), sa.Column("candidates_normalized_count", 
        sa.Integer, nullable=False, server_default="0"), sa.Column("candidates_persisted_count", 
        sa.Integer, nullable=False, server_default="0"), sa.Column("companies_created", sa.Integer, 
        nullable=False, server_default="0"), sa.Column("companies_merged", sa.Integer, 
        nullable=False, server_default="0"), sa.Column("contacts_created", sa.Integer, 
        nullable=False, server_default="0"), sa.Column("contacts_merged", sa.Integer, 
        nullable=False, server_default="0"), sa.Column("total_cost_usd", sa.Float, nullable=False, 
        server_default="0"), sa.Column("duration_ms", sa.Integer, nullable=True), sa.Column("error", 
        sa.Text, nullable=True), sa.Column("error_stage", sa.String(32), nullable=True), 
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True), sa.Column("finished_at", 
        sa.DateTime(timezone=True), nullable=True), sa.Column("trace_id", sa.String(64), 
        nullable=True), sa.Column("schema_version", sa.String(16), nullable=False, 
        server_default="1.0"), sa.Column("metadata", postgresql.JSONB, nullable=False, 
        server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, 
        server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), 
        nullable=False, server_default=sa.func.now()),
    ) op.create_index("ix_search_jobs_tenant_status", "search_jobs", ["tenant_id", "status"]) 
    op.create_index("ix_search_jobs_tenant_icp", "search_jobs", ["tenant_id", "icp_id"]) 
    op.create_index("ix_search_jobs_tenant_created", "search_jobs", ["tenant_id", "created_at"]) 
    op.create_table(
        "search_job_items", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), 
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("job_id", 
        postgresql.UUID(as_uuid=True), sa.ForeignKey("search_jobs.id", ondelete="CASCADE"), 
        nullable=False), sa.Column("source", sa.String(32), nullable=False), sa.Column("source_url", 
        sa.Text, nullable=True), sa.Column("raw_payload", postgresql.JSONB, nullable=False, 
        server_default="{}"), sa.Column("normalized_company", postgresql.JSONB, nullable=True), 
        sa.Column("normalized_contacts", postgresql.JSONB, nullable=True), sa.Column("score", 
        sa.Float, nullable=True), sa.Column("score_breakdown", postgresql.JSONB, nullable=True), 
        sa.Column("status", sa.String(32), nullable=False, server_default="raw"), 
        sa.Column("skip_reason", sa.String(128), nullable=True), sa.Column("error", sa.Text, 
        nullable=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True), 
        sa.Column("contact_ids", postgresql.JSONB, nullable=True), sa.Column("created_at", 
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), 
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, 
        server_default=sa.func.now()),
    ) op.create_index("ix_search_job_items_job", "search_job_items", ["job_id"]) 
    op.create_index("ix_search_job_items_tenant_status", "search_job_items", ["tenant_id", 
    "status"]) op.create_index("ix_search_job_items_score", "search_job_items", ["tenant_id", 
    "score"]) for table in ["search_jobs", "search_job_items"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY") op.execute(f""" CREATE POLICY 
            {table}_tenant_isolation ON {table} USING (tenant_id = current_setting('app.tenant_id', 
            true)::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """) ```
### Добавить в `infra/docker-compose.dev.yml`
```yaml sourcing-service: <<: *service-defaults build: context: .. dockerfile: 
      services/sourcing-service/Dockerfile
    container_name: outreach-sourcing-service environment: <<: *common-env SERVICE_NAME: 
      sourcing-service SERVICE_PORT: "8000" DATABASE_URL: 
      postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach} 
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222 REDIS_URL: 
      redis://:${REDIS_PASSWORD}@redis:6379/5 ICP_SERVICE_URL: http://icp-service:8000 
      CONTACT_STORE_URL: http://contact-store:8000 LLM_GATEWAY_URL: http://llm-gateway:8000 
      SERPER_API_KEY: ${SERPER_API_KEY:-} YANDEX_XML_USER: ${YANDEX_XML_USER:-} YANDEX_XML_KEY: 
      ${YANDEX_XML_KEY:-} LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on: postgres: condition: service_healthy nats: condition: service_healthy redis: 
        condition: service_healthy
      icp-service: condition: service_started contact-store: condition: service_started labels: 
      caddy: sourcing.dev.aitler.ru caddy.reverse_proxy: "{{upstreams 8000}}"
    healthcheck: test: ["CMD", "python", "-c", "import urllib.request; 
      urllib.request.urlopen('http://localhost:8000/healthz')"] interval: 10s timeout: 5s retries: 5 
      start_period: 15s
``` **Обновить `.env.example`:** ```bash
# Sourcing — Serper
SERPER_API_KEY= SERPER_BASE_URL=https://google.serper.dev
# Sourcing — Yandex XML
YANDEX_XML_USER= YANDEX_XML_KEY= ``` **Обновить `scripts/migrate.sh`** — добавить 
`sourcing-service`.
## Acceptance criteria
```bash
# 1. Миграция
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm sourcing-service alembic 
upgrade head
# Ожидание: Applying 0001_create_search_jobs... OK 2. Сервис поднимается
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d sourcing-service
# Ожидание: service_started 3. Healthcheck
curl -fsS https://sourcing.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"} 4. Таблицы + RLS
bash scripts/psql.sh -c "\dt search_*" bash scripts/psql.sh -c "SELECT tablename, rowsecurity FROM 
pg_tables WHERE tablename LIKE 'search_%';"
# Ожидание: обе таблицы, rowsecurity=true 5. OpenAPI
curl -fsS https://sourcing.dev.aitler.ru/openapi.json | jq .info.title
# Ожидание: "Sourcing Service"
```
## Подсказки
- **`SearchJobItem`** — не удалять после persist. Это история. Для retry и для аналитики «сколько 
кандидатов дал каждый источник». - **`progress`** — JSONB, обновляется часто. Если станет bottleneck 
— вынести в Redis. Пока БД. - **`params`** — гибкая структура. Источники определяются динамически. - 
**Не делать `search_jobs` огромной** — если будет много поисков, добавим retention policy (удалять 
completed > 90 дней).
## Анти-паттерны
- ❌ Не хранить сырые результаты кандидатов только в `search_jobs.params` — они в 
`search_job_items`. - ❌ Не забывать RLS. - ❌ Не делать `segment_id` UUID-типом — это строка (UUID 
из ICP payload, не FK). ---
# Задача 2C.1.2 — Абстракция Connector + Registry
**Файл:** `docs/tasks/sprint-2c/2c.1.2-connectors.md`
## Цель
Определить базовый интерфейс `Connector`, тип `RawCandidate`, `ConnectorRegistry`. Без реализации 
конкретных коннекторов.
## Зависимости
2C.1.1.
## Что создать
``` services/sourcing-service/src/sourcing_service/connectors/ ├── __init__.py ├── base.py ├── 
registry.py └── exceptions.py ```
## Детали
### `base.py`
```python from abc import ABC, abstractmethod from dataclasses import dataclass, field from datetime 
import datetime, timezone from typing import Any @dataclass class RawCandidate:
    """Сырой кандидат от коннектора. Не нормализован, не скорирован.""" source: str # "serper" | 
    "yandex_xml" | "rusprofile" | ... source_url: str | None title: str | None = None snippet: str | 
    None = None domain: str | None = None raw_payload: dict[str, Any] = field(default_factory=dict)
    # raw_payload — оригинальный ответ источника (для отладки и повторной обработки)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc)) def 
    dedup_key(self) -> str:
        """Ключ для дедупа между коннекторами.""" if self.domain: return 
            f"domain:{self.domain.lower()}"
        if self.source_url: return f"url:{self.source_url.lower()}" return 
        f"title:{self.title}:{self.source}"
@dataclass class SearchCriteria: """Критерии поиска. Формируются оркестратором из ICP-сегмента."""
    # Что искать
    keywords: list[str] # основные поисковые запросы negative_keywords: list[str] = 
    field(default_factory=list)
    # Где искать
    geo: list[str] = field(default_factory=list) # ["RU"] language: str = "ru"
    # Ограничения
    limit: int = 50 domain_whitelist: list[str] | None = None # если ищем только по конкретным 
    сайтам domain_blacklist: list[str] = field(default_factory=list)
    # Дополнительно
    extra: dict[str, Any] = field(default_factory=dict) @dataclass class ConnectorResult: 
    """Результат работы коннектора.""" source: str candidates: list[RawCandidate] cost_usd: float = 
    0.0 error: str | None = None duration_ms: int = 0 meta: dict[str, Any] = 
    field(default_factory=dict)
class Connector(ABC): """Базовый интерфейс коннектора. Коннектор ТОЛЬКО достаёт данные из источника. 
    Не нормализует, не скорит, не пишет в БД. """ name: str # уникальное имя, используется в 
    registry def __init__(self, *, rate_limit_per_sec: float = 5.0, timeout: float = 30.0) -> None:
        self._rate_limit = rate_limit_per_sec self._timeout = timeout @abstractmethod async def 
    search(self, criteria: SearchCriteria) -> ConnectorResult:
        """Основной метод. Возвращает сырых кандидатов.""" ... async def close(self) -> None: 
        """Опционально: закрыть HTTP-клиенты.""" return None
    @property def is_available(self) -> bool: """Готов ли коннектор к работе (есть ключи, не в 
        блэклисте).""" return True
    @property def cost_per_call_usd(self) -> float: """Оценка стоимости одного вызова (для budget 
        tracking).""" return 0.0
```
### `exceptions.py`
```python class ConnectorError(Exception): """Базовая ошибка коннектора.""" class 
ConnectorUnavailableError(ConnectorError):
    """Коннектор недоступен (нет ключей, API упал).""" class 
ConnectorRateLimitError(ConnectorError):
    """Rate limit исчерпан.""" class ConnectorAuthError(ConnectorError): """Проблема с 
    аутентификацией (неверный ключ)."""
```
### `registry.py`
```python from sourcing_service.connectors.base import Connector from 
sourcing_service.connectors.exceptions import ConnectorUnavailableError class ConnectorRegistry:
    """Реестр коннекторов. Зарегистрированные доступны по имени.""" def __init__(self) -> None: 
        self._connectors: dict[str, Connector] = {}
    def register(self, connector: Connector) -> None: if connector.name in self._connectors: raise 
            ValueError(f"Connector already registered: {connector.name}")
        self._connectors[connector.name] = connector def get(self, name: str) -> Connector: if name 
        not in self._connectors:
            raise ConnectorUnavailableError(f"Connector not registered: {name}") return 
        self._connectors[name]
    def list_all(self) -> list[str]: return list(self._connectors.keys()) def list_available(self) 
    -> list[str]:
        return [name for name, c in self._connectors.items() if c.is_available] async def 
    close_all(self) -> None:
        for c in self._connectors.values(): await c.close() ``` **Регистрация коннекторов — в 
`main.py`** через lifespan. Коннекторы создаются с настройками из `Settings`.
## Acceptance criteria
```bash uv run python -c " from sourcing_service.connectors.base import Connector, RawCandidate, 
SearchCriteria, ConnectorResult from sourcing_service.connectors.registry import ConnectorRegistry 
from sourcing_service.connectors.exceptions import ConnectorError, ConnectorUnavailableError 
print('OK') " uv run mypy services/sourcing-service uv run ruff check services/sourcing-service ```
## Подсказки
- **`RawCandidate.dedup_key()`** — критично для дедупа между коннекторами. Если Serper и Yandex 
вернули один сайт — обрабатываем один раз. - **`ConnectorResult`** содержит `cost_usd` — для cost 
tracking. - **`is_available`** — коннектор без API-ключа не должен попадать в поиск. Логика: в 
`SearchOrchestrator` фильтруем по `available`. - **Не забыть `close_all()`** при shutdown.
## Анти-паттерны
- ❌ Не делать коннекторы stateful (кроме HTTP-клиента и rate-limiter'а). - ❌ Не позволять 
коннектору самому решать, что делать с данными — только «достать». - ❌ Не забывать про rate limit — 
каждый коннектор сам его соблюдает. ---
# Задача 2C.1.3 — `WebSearchConnector` (Serper + Yandex XML)
**Файл:** `docs/tasks/sprint-2c/2c.1.3-web-search.md`
## Цель
Реализовать два коннектора: Serper (Google Search API) и Yandex XML (поиск). Оба — «поиск по 
ключевым словам с гео-таргетингом», возвращают URL + title + snippet.
## Зависимости
2C.1.2.
## Что создать
``` services/sourcing-service/src/sourcing_service/connectors/ ├── serper.py └── yandex_xml.py 
services/sourcing-service/tests/ ├── test_serper.py └── test_yandex_xml.py ```
## Детали
### `serper.py`
```python import asyncio import time from collections import deque from typing import Any import 
httpx import structlog from tenacity import retry, stop_after_attempt, wait_exponential, 
retry_if_exception_type from sourcing_service.connectors.base import (
    Connector, ConnectorResult, RawCandidate, SearchCriteria, ) from 
sourcing_service.connectors.exceptions import (
    ConnectorAuthError, ConnectorRateLimitError, ConnectorUnavailableError, ) logger = 
structlog.get_logger() class _RateLimiter:
    """Простейший rate limiter — не больше N запросов в секунду.""" def __init__(self, per_sec: 
    float) -> None:
        self._interval = 1.0 / per_sec if per_sec > 0 else 0.0 self._last = 0.0 self._lock = 
        asyncio.Lock()
    async def acquire(self) -> None: if self._interval <= 0: return async with self._lock: now = 
            time.monotonic() wait = self._last + self._interval - now if wait > 0:
                await asyncio.sleep(wait) self._last = time.monotonic() class 
SerperConnector(Connector):
    """Google Search через Serper.dev API. Docs: https://serper.dev/ Cost: ~$0.30 per 1000 queries 
    (примерно). """ name = "serper" COST_PER_CALL_USD = 0.0003 def __init__(self, *, api_key: str, 
    base_url: str, rate_limit_per_sec: float = 5.0) -> None:
        super().__init__(rate_limit_per_sec=rate_limit_per_sec) self._api_key = api_key self._client 
        = httpx.AsyncClient(
            base_url=base_url, headers={"X-API-KEY": api_key, "Content-Type": "application/json"}, 
            timeout=httpx.Timeout(30.0, connect=5.0),
        ) self._limiter = _RateLimiter(rate_limit_per_sec) @property def is_available(self) -> bool: 
        return bool(self._api_key)
    @property def cost_per_call_usd(self) -> float: return self.COST_PER_CALL_USD async def 
    search(self, criteria: SearchCriteria) -> ConnectorResult:
        if not self.is_available: raise ConnectorUnavailableError("Serper API key not set") started 
        = time.monotonic() candidates: list[RawCandidate] = [] seen_domains: set[str] = set() 
        errors: list[str] = [] for query in criteria.keywords[:5]: # не больше 5 запросов на поиск
            try: await self._limiter.acquire() results = await self._search_one(query, criteria) for 
                item in results:
                    domain = self._extract_domain(item.get("link", "")) if not domain or domain in 
                    seen_domains:
                        continue if domain in criteria.domain_blacklist: continue if 
                    criteria.domain_whitelist and domain not in criteria.domain_whitelist:
                        continue seen_domains.add(domain) candidates.append(RawCandidate( 
                        source=self.name, source_url=item.get("link"), title=item.get("title"), 
                        snippet=item.get("snippet"), domain=domain, raw_payload=item,
                    )) if len(candidates) >= criteria.limit: break if len(candidates) >= 
                criteria.limit:
                    break except Exception as e: logger.warning("serper_query_failed", query=query, 
                error=str(e)) errors.append(f"{query}: {e}")
        duration_ms = int((time.monotonic() - started) * 1000) cost = self.COST_PER_CALL_USD * 
        min(len(criteria.keywords), 5) return ConnectorResult(
            source=self.name, candidates=candidates, cost_usd=cost, error="; ".join(errors) if 
            errors else None, duration_ms=duration_ms,
        ) @retry( stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), 
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)), reraise=True,
    ) async def _search_one(self, query: str, criteria: SearchCriteria) -> list[dict]:
        # Гео-параметры
        gl = criteria.geo[0].lower() if criteria.geo else "ru" hl = criteria.language
        # Serper не поддерживает несколько гео в одном запросе — используем первое
        payload = { "q": query, "gl": gl, "hl": hl, "num": min(criteria.limit, 100),
        }
        resp = await self._client.post("/search", json=payload) if resp.status_code == 401 or 
        resp.status_code == 403:
            raise ConnectorAuthError(f"Serper auth failed: {resp.status_code}") if resp.status_code 
        == 429:
            raise ConnectorRateLimitError("Serper rate limit") resp.raise_for_status() data = 
        resp.json() return data.get("organic", [])
    @staticmethod def _extract_domain(url: str) -> str | None: if not url: return None import 
        tldextract ext = tldextract.extract(url) if not ext.domain or not ext.suffix:
            return None return f"{ext.domain}.{ext.suffix}".lower() async def close(self) -> None: 
        await self._client.aclose()
```
### `yandex_xml.py`
Yandex XML — официальный поиск Яндекса для разработчиков. Формат ответа — XML. ```python import time 
from typing import Any from xml.etree import ElementTree as ET import httpx import structlog from 
tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type from 
sourcing_service.connectors.base import (
    Connector, ConnectorResult, RawCandidate, SearchCriteria, ) from 
sourcing_service.connectors.exceptions import (
    ConnectorAuthError, ConnectorRateLimitError, ConnectorUnavailableError, ) logger = 
structlog.get_logger() class YandexXMLConnector(Connector):
    """Yandex XML Search API. Docs: https://yandex.ru/dev/xml/ Cost: ~$0.0006 per query (зависит от 
    тарифа). """ name = "yandex_xml" ENDPOINT = "https://yandex.com/search/xml" COST_PER_CALL_USD = 
    0.0006 def __init__(self, *, user: str, key: str, rate_limit_per_sec: float = 1.0) -> None:
        super().__init__(rate_limit_per_sec=rate_limit_per_sec) self._user = user self._key = key 
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    @property def is_available(self) -> bool: return bool(self._user and self._key) @property def 
    cost_per_call_usd(self) -> float:
        return self.COST_PER_CALL_USD async def search(self, criteria: SearchCriteria) -> 
    ConnectorResult:
        if not self.is_available: raise ConnectorUnavailableError("Yandex XML credentials not set") 
        started = time.monotonic() candidates: list[RawCandidate] = [] seen_domains: set[str] = 
        set() errors: list[str] = [] for query in criteria.keywords[:5]:
            try: results = await self._search_one(query, criteria) for item in results: domain = 
                    self._extract_domain(item.get("url", "")) if not domain or domain in 
                    seen_domains:
                        continue if domain in criteria.domain_blacklist: continue if 
                    criteria.domain_whitelist and domain not in criteria.domain_whitelist:
                        continue seen_domains.add(domain) candidates.append(RawCandidate( 
                        source=self.name, source_url=item.get("url"), title=item.get("title"), 
                        snippet=item.get("snippet"), domain=domain, raw_payload=item,
                    )) if len(candidates) >= criteria.limit: break if len(candidates) >= 
                criteria.limit:
                    break except Exception as e: logger.warning("yandex_xml_query_failed", 
                query=query, error=str(e)) errors.append(f"{query}: {e}")
        duration_ms = int((time.monotonic() - started) * 1000) cost = self.COST_PER_CALL_USD * 
        min(len(criteria.keywords), 5) return ConnectorResult(
            source=self.name, candidates=candidates, cost_usd=cost, error="; ".join(errors) if 
            errors else None, duration_ms=duration_ms,
        ) @retry( stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), 
        retry=retry_if_exception_type((httpx.TransportError,)), reraise=True,
    ) async def _search_one(self, query: str, criteria: SearchCriteria) -> list[dict]: params = { 
            "user": self._user, "key": self._key, "query": query, "lr": 
            self._geo_to_yandex_region(criteria.geo), "l10n": criteria.language, "sortby": "rlv", 
            "filter": "strict", "groupby": "attr=d.mode=deep.groups-on-page=10.docs-in-group=1", 
            "maxpassages": "3", "page": "0",
        }
        resp = await self._client.get(self.ENDPOINT, params=params) if resp.status_code == 401 or 
        resp.status_code == 403:
            raise ConnectorAuthError(f"Yandex XML auth failed: {resp.status_code}") if 
        resp.status_code == 429:
            raise ConnectorRateLimitError("Yandex XML rate limit") resp.raise_for_status() try: root 
            = ET.fromstring(resp.text)
        except ET.ParseError as e: raise ConnectorRateLimitError(f"Yandex XML parse error: {e}") 
            from e
        # Проверка ошибок в ответе
        error_el = root.find(".//error") if error_el is not None: code = error_el.get("code", "") if 
            code in ("15", "32", "33"):
                raise ConnectorRateLimitError(f"Yandex XML error: {code}") raise 
            ConnectorAuthError(f"Yandex XML error: {code} {error_el.text}")
        results: list[dict] = [] for doc in root.findall(".//doc"): url_el = doc.find("url") 
            title_el = doc.find("title") passages = doc.findall(".//passage") snippet = " 
            ".join(p.text or "" for p in passages if p.text) results.append({
                "url": url_el.text if url_el is not None else None, "title": title_el.text if 
                title_el is not None else None, "snippet": snippet,
            })
        return results @staticmethod def _geo_to_yandex_region(geos: list[str]) -> str: """Yandex 
        XML использует числовые ID регионов. Упрощённо: RU=225, KZ=159, BY=149, UA=187.""" if not 
        geos:
            return "225" mapping = {"RU": "225", "KZ": "159", "BY": "149", "UA": "187"} return 
        mapping.get(geos[0].upper(), "225")
    @staticmethod def _extract_domain(url: str) -> str | None: if not url: return None import 
        tldextract ext = tldextract.extract(url) if not ext.domain or not ext.suffix:
            return None return f"{ext.domain}.{ext.suffix}".lower() async def close(self) -> None: 
        await self._client.aclose()
```
### Регистрация в `main.py`
```python from sourcing_service.connectors.registry import ConnectorRegistry from 
sourcing_service.connectors.serper import SerperConnector from 
sourcing_service.connectors.yandex_xml import YandexXMLConnector
# в lifespan:
registry = ConnectorRegistry() registry.register(SerperConnector( api_key=settings.serper_api_key, 
    base_url=settings.serper_base_url, rate_limit_per_sec=settings.serper_rate_limit_per_sec,
)) registry.register(YandexXMLConnector( user=settings.yandex_xml_user, key=settings.yandex_xml_key, 
)) app.state.connector_registry = registry
# при shutdown:
await registry.close_all() ```
### Тесты
`tests/test_serper.py` — с respx: ```python import pytest import respx from httpx import Response 
from sourcing_service.connectors.base import SearchCriteria from sourcing_service.connectors.serper 
import SerperConnector @pytest.mark.asyncio @respx.mock async def test_serper_search_success():
    respx.post("https://google.serper.dev/search").mock( return_value=Response(200, json={ 
            "organic": [
                {"link": "https://romashka.ru/about", "title": "Ромашка", "snippet": 
                "Производство"}, {"link": "https://romashka.ru/contacts", "title": "Контакты", 
                "snippet": "..."}, # дубликат домена {"link": "https://test.com", "title": "Test", 
                "snippet": "..."},
            ]
        })
    ) connector = SerperConnector(api_key="test", base_url="https://google.serper.dev", 
    rate_limit_per_sec=1000) criteria = SearchCriteria(keywords=["гидроборты дистрибьютор"], 
    geo=["RU"], language="ru", limit=10) result = await connector.search(criteria) assert 
    len(result.candidates) == 2 # дубликат домена убран assert result.candidates[0].domain == 
    "romashka.ru" await connector.close()
@pytest.mark.asyncio async def test_serper_unavailable_without_key(): connector = 
    SerperConnector(api_key="", base_url="https://google.serper.dev") assert not 
    connector.is_available await connector.close()
```
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/test_serper.py 
services/sourcing-service/tests/test_yandex_xml.py -v
# Ожидание: все passed E2E с реальным Serper (если ключ есть)
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev exec -T sourcing-service python - 
<<'PY' import asyncio from sourcing_service.config import Settings from 
sourcing_service.connectors.base import SearchCriteria from sourcing_service.connectors.serper 
import SerperConnector async def main():
    s = Settings() c = SerperConnector(api_key=s.serper_api_key, base_url=s.serper_base_url) 
    criteria = SearchCriteria(keywords=["гидроборты производитель"], geo=["RU"], limit=10) result = 
    await c.search(criteria) print(f"Got {len(result.candidates)} candidates") for cand in 
    result.candidates[:3]:
        print(f" - {cand.domain}: {cand.title}") await c.close() asyncio.run(main()) PY
# Ожидание: 5-10 кандидатов с реальными доменами
```
## Подсказки
- **Rate limiter** — простейший, но работает. Для высоких нагрузок использовать `aiolimiter`. - 
**Дедуп по домену** — критично. Serper и Yandex часто возвращают несколько страниц одного сайта. - 
**`tldextract`** — обязателен. Наивный `urlparse().netloc` не отсекает `www.` и поддомены. - 
**Yandex XML** — требует регистрации приложения на https://xml.yandex.ru/. Получить `user` и `key`. 
Лимиты разные для разных тарифов.
## Анти-паттерны
- ❌ Не делать коннектор без rate limiter. - ❌ Не возвращать дубликаты по домену. - ❌ Не падать 
при ошибке одного запроса — собирать errors и продолжать. - ❌ Не логировать полные ответы API 
(могут быть большие). ---
# Задача 2C.1.4 — `Normalizer` (LLM: RawCandidate → Company/Contact)
**Файл:** `docs/tasks/sprint-2c/2c.1.4-normalizer.md`
## Цель
Реализовать LLM-нормализатор: превращает `RawCandidate` (URL + title + snippet) в структурированную 
Company + контакты (если есть). Evidence сохраняется.
## Зависимости
2C.1.2.
## Что создать
``` services/sourcing-service/src/sourcing_service/ ├── llm/ │ ├── client.py # копия из 
brief-service │ ├── json_utils.py # копия │ ├── schemas.py # схемы ответа LLM │ └── prompts/ │ ├── 
__init__.py │ ├── base.py │ └── normalize_candidate.py └── normalization/
    ├── __init__.py └── normalizer.py ```
### `llm/schemas.py`
```python from pydantic import BaseModel, ConfigDict, Field class _Evidence(BaseModel): model_config 
    = ConfigDict(extra="ignore") source_url: str | None = None source_type: str = "website" snippet: 
    str | None = None
class _Fact(BaseModel): model_config = ConfigDict(extra="ignore") value: str | int | float | None = 
    None confidence: float = Field(0.5, ge=0.0, le=1.0) evidence: list[_Evidence] = 
    Field(default_factory=list)
class _CompanyName(BaseModel): model_config = ConfigDict(extra="ignore") value: str | None = None 
    confidence: float = Field(0.5, ge=0.0, le=1.0) evidence: list[_Evidence] = 
    Field(default_factory=list)
class _CompanyDomain(BaseModel): model_config = ConfigDict(extra="ignore") value: str | None = None 
    confidence: float = Field(0.5, ge=0.0, le=1.0) evidence: list[_Evidence] = 
    Field(default_factory=list)
class _EmailItem(BaseModel): model_config = ConfigDict(extra="ignore") value: str type: str = 
    "unknown" is_primary: bool = False confidence: float = Field(0.5, ge=0.0, le=1.0) evidence: 
    list[_Evidence] = Field(default_factory=list)
class _PhoneItem(BaseModel): model_config = ConfigDict(extra="ignore") value: str type: str = 
    "unknown" is_primary: bool = False confidence: float = Field(0.5, ge=0.0, le=1.0) evidence: 
    list[_Evidence] = Field(default_factory=list)
class _ContactItem(BaseModel): model_config = ConfigDict(extra="ignore") full_name: str position: 
    str | None = None role_category: str = "unknown" seniority: str = "unknown" emails: 
    list[_EmailItem] = Field(default_factory=list) phones: list[_PhoneItem] = 
    Field(default_factory=list) confidence: float = Field(0.5, ge=0.0, le=1.0)
class _NormalizedCandidate(BaseModel): """Результат нормализации одного RawCandidate.""" 
    model_config = ConfigDict(extra="ignore") is_company: bool = True is_relevant: bool = True 
    relevance_reason: str = "" company: dict = Field(default_factory=dict)
    # {name, domain, website, industry, sub_industry, size_estimate, locations, registry_ids, ...}
    contacts: list[_ContactItem] = Field(default_factory=list) ``` **Важно:** `company` — свободный 
dict, потому что структура большая, а валидировать полностью через Pydantic — оверинжиниринг. 
Ключевые поля проверяем в `normalizer.py` при конвертации в `contracts.Company`.
### `llm/prompts/normalize_candidate.py`
```python from sourcing_service.llm.prompts.base import SYSTEM_NORMALIZER, Prompt def 
build_normalize_prompt(
    *, candidate_title: str | None, candidate_snippet: str | None, candidate_url: str | None, 
    candidate_domain: str | None, segment_context: str, candidate_extra: str | None = None,
) -> Prompt: user = f"""Ты — эксперт по нормализации данных о компаниях из результатов поиска. 
Контекст: мы ищем компании для сегмента ICP: <segment> {segment_context} </segment> Найден кандидат: 
- URL: {candidate_url or '(нет)'} - Домен: {candidate_domain or '(нет)'} - Заголовок: 
{candidate_title or '(нет)'} - Сниппет: {candidate_snippet or '(нет)'} {f'- Дополнительно: 
{candidate_extra}' if candidate_extra else ''} Задача: определить, является ли это релевантной 
компанией для нашего ICP. Если да — нормализовать. Правила: 1. is_company: true, если это сайт 
компании (не статья, не каталог, не маркетплейс). 2. is_relevant: true, если компания подходит под 
сегмент. Иначе false + relevance_reason. 3. company.name — название компании. Если не удаётся 
извлечь — null. 4. company.domain — домен без www и протокола. 5. company.website — полный URL. 6. 
company.industry, company.sub_industry — если определяются из заголовка/сниппета. Иначе null. 7. 
company.locations — массив объектов со страной/городом, если известны. 8. contacts — если в сниппете 
есть упоминания людей (ФИО, должности, email, телефон). Если нет — пустой массив. 9. Для каждого 
поля — confidence 0.0-1.0 и evidence с source_url=URL кандидата. 10. Не выдумывай данные. Если не 
знаешь — null. Верни JSON ровно такой структуры (без markdown, без пояснений): {{
  "is_company": true, "is_relevant": true, "relevance_reason": "string", "company": {{ "name": 
    {{"value": "string | null", "confidence": 0.0-1.0, "evidence": [{{"source_url": "string", 
    "source_type": "search", "snippet": "string"}}]}}, "domain": {{...}}, "website": {{...}}, 
    "industry": {{...}}, "sub_industry": {{...}}, "locations": []
  }},
  "contacts": [ {{ "full_name": "string", "position": "string | null", "role_category": 
      "decision_maker | influencer | gatekeeper | champion | unknown", "seniority": "c_level | vp | 
      director | manager | specialist | unknown", "emails": [{{"value": "string", "type": "work", 
      "is_primary": true, "confidence": 0.0-1.0, "evidence": []}}], "phones": [{{"value": "string", 
      "type": "work", "is_primary": true, "confidence": 0.0-1.0, "evidence": []}}], "confidence": 
      0.0-1.0
    }}
  ]
}}
""" return Prompt( system=SYSTEM_NORMALIZER, user=user, task_type="sourcing_normalize_candidate_v1", 
    )
```
### `llm/prompts/base.py`
```python from dataclasses import dataclass @dataclass(frozen=True) class Prompt: system: str user: 
    str task_type: str
SYSTEM_NORMALIZER = """Ты — эксперт по нормализации данных о компаниях из результатов поиска. 
Правила: - Отвечай ТОЛЬКО валидным JSON, без markdown-обёрток и пояснений. - Если данных нет — 
используй null или пустой массив. Не выдумывай. - Названия компаний и должности — на языке 
оригинала. - Confidence: 0.9+ — если явно в заголовке; 0.7-0.9 — если в сниппете; 0.5-0.7 — вывод; 
<0.5 — не уверен. - Evidence обязателен для каждого поля. source_url = URL кандидата. """ ```
### `normalization/normalizer.py`
```python from uuid import UUID from uuid6 import uuid7 import structlog from common.context import 
get_trace_id from sourcing_service.connectors.base import RawCandidate from 
sourcing_service.llm.client import LLMClient from sourcing_service.llm.prompts.normalize_candidate 
import build_normalize_prompt from sourcing_service.llm.schemas import _NormalizedCandidate from 
icp_service.models import ICP # НЕТ! cross-service import запрещён. См. ниже. logger = 
structlog.get_logger() class Normalizer:
    """Превращает RawCandidate в структурированный Company + Contacts через LLM.""" def 
    __init__(self, llm: LLMClient) -> None:
        self._llm = llm async def normalize( self, candidate: RawCandidate, *, tenant_id: UUID, 
        segment_context: str,
    ) -> _NormalizedCandidate: prompt = build_normalize_prompt( candidate_title=candidate.title, 
            candidate_snippet=candidate.snippet, candidate_url=candidate.source_url, 
            candidate_domain=candidate.domain, segment_context=segment_context,
        ) result = await self._llm.complete_json( tenant_id=str(tenant_id), 
            task_type=prompt.task_type, system=prompt.system, user=prompt.user, 
            output_schema=_NormalizedCandidate, trace_id=get_trace_id() or "",
        ) return result async def normalize_batch( self, candidates: list[RawCandidate], *, 
        tenant_id: UUID, segment_context: str, max_concurrency: int = 5,
    ) -> list[tuple[RawCandidate, _NormalizedCandidate | None, str | None]]: """Нормализует батч 
        параллельно. Возвращает [(candidate, result|None, error|None)].""" import asyncio sem = 
        asyncio.Semaphore(max_concurrency) results: list[tuple[RawCandidate, _NormalizedCandidate | 
        None, str | None]] = [] async def _one(c: RawCandidate) -> tuple[RawCandidate, 
        _NormalizedCandidate | None, str | None]:
            async with sem: try: r = await self.normalize(c, tenant_id=tenant_id, 
                    segment_context=segment_context) return (c, r, None)
                except Exception as e: logger.warning("normalize_failed", candidate=c.source_url, 
                    error=str(e)) return (c, None, str(e))
        tasks = [_one(c) for c in candidates] for coro in asyncio.as_completed(tasks): 
            results.append(await coro)
        return results ``` **Важно:** никаких cross-service импортов. `ICP` не импортируем. 
`segment_context` передаётся строкой — её готовит `SearchOrchestrator` из ICP payload.
### Тесты
`tests/test_normalizer.py` — с respx на llm-gateway: ```python @pytest.mark.asyncio @respx.mock 
async def test_normalize_company():
    respx.post("http://llm-gateway:8000/v1/complete").mock( return_value=Response(200, json={ 
            "text": 
            '{"is_company":true,"is_relevant":true,"relevance_reason":"Производство","company":{"name":{"value":"Ромашка","confidence":0.9,"evidence":[{"source_url":"https://romashka.ru","source_type":"search","snippet":"..."}]},"domain":{"value":"romashka.ru","confidence":0.9,"evidence":[]},"industry":{"value":"Производство","confidence":0.7,"evidence":[]}},"contacts":[]}', 
            "model": "deepseek-chat", "tokens_in": 500, "tokens_out": 200, "cost_usd": 0.0002, 
            "latency_ms": 1500,
        })
    )
    # ... тест
```
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/test_normalizer.py -v
# Ожидание: passed
uv run mypy services/sourcing-service uv run ruff check services/sourcing-service ```
## Подсказки
- **Не импортировать `ICP` из icp_service** — это cross-service. `segment_context` — строка. - 
**`normalize_batch` с семафором** — не больше 5 LLM-вызовов одновременно. Иначе rate limit и cost. - 
**Ошибка нормализации одного кандидата** не должна ронять весь батч. Собираем errors. - **Evidence 
обязателен** — иначе нельзя проверить, откуда взято поле.
## Анти-паттерны
- ❌ Не парсить JSON от LLM без `complete_json` (валидация через Pydantic). - ❌ Не запускать 
`normalize_batch` без ограничения concurrency. - ❌ Не импортировать модели из других сервисов. ---
# Задача 2C.1.5 — `SearchOrchestrator` + API endpoint + E2E
**Файл:** `docs/tasks/sprint-2c/2c.1.5-orchestrator.md`
## Цель
Связать всё: ICP → коннекторы → дедуп → нормализация → persist в contact-store. API: `POST 
/searches`, `GET /searches/{id}`, `POST /searches/{id}/cancel`. E2E с одним источником (Serper).
## Зависимости
2C.1.1–2C.1.4.
## Что создать
- `clients/icp_client.py`, `clients/contact_store_client.py`. - `scoring/scorer.py` (минимальный — 
просто заглушка, полноценный в 2C.3). - `service.py` — `SearchOrchestrator`. - `schemas.py` — 
API-схемы. - `api/routes.py`, `api/deps.py`. - `events.py`. - Обновить `main.py`. - Тесты + E2E.
## Детали
### `clients/icp_client.py`
```python import httpx import structlog from tenacity import retry, stop_after_attempt, 
wait_exponential, retry_if_exception_type from common.errors import AppError logger = 
structlog.get_logger() class ICPNotFoundError(AppError):
    code = "icp_not_found" status_code = 404 message = "ICP not found" class ICPClient: def 
    __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(30.0, 
        connect=5.0))
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5), 
    retry=retry_if_exception_type(httpx.TransportError), reraise=True) async def get_icp(self, 
    icp_id: str, *, tenant_id: str, trace_id: str = "") -> dict:
        resp = await self._client.get( f"/icps/{icp_id}", headers={"X-Tenant-ID": tenant_id, 
            "X-Trace-Id": trace_id},
        ) if resp.status_code == 404: raise ICPNotFoundError(f"ICP {icp_id} not found") 
        resp.raise_for_status() return resp.json()
    async def close(self) -> None: await self._client.aclose() ```
### `clients/contact_store_client.py`
```python class ContactStoreClient: def __init__(self, base_url: str) -> None: self._client = 
        httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(60.0, connect=5.0))
    async def upsert_company( self, *, tenant_id: str, payload: dict, trace_id: str = "", 
        idempotency_key: str,
    ) -> tuple[dict | None, str]: """Возвращает (company, action). action: created | updated | 
        merged.""" resp = await self._client.post(
            "/companies", json={"payload": payload}, headers={ "X-Tenant-ID": tenant_id, 
                "X-Trace-Id": trace_id, "Idempotency-Key": idempotency_key,
            },
        ) if resp.status_code not in (200, 201): raise AppError(f"contact-store upsert failed: 
            {resp.status_code} {resp.text}", code="contact_store_error", status_code=502)
        data = resp.json() return data.get("company"), data.get("action", "created") async def 
    upsert_contact(
        self, *, tenant_id: str, payload: dict, trace_id: str = "", idempotency_key: str, ) -> 
    tuple[dict | None, str]:
        resp = await self._client.post( "/contacts", json={"payload": payload}, headers={ 
                "X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id, "Idempotency-Key": 
                idempotency_key,
            },
        ) if resp.status_code == 409:
            # blocked by stoplist
            data = resp.json() return None, f"blocked:{data.get('reason', 'unknown')}" if 
        resp.status_code not in (200, 201):
            raise AppError(f"contact-store upsert failed: {resp.status_code}", 
            code="contact_store_error", status_code=502)
        data = resp.json() return data.get("contact"), data.get("action", "created") async def 
    close(self) -> None:
        await self._client.aclose() ```
### `scoring/scorer.py` (минимальный на 2C.1)
```python from icp_service_contract import SegmentWeights # нет, это не так class Scorer: 
    """Заглушка. Полноценный скоринг — в 2C.3.""" def __init__(self, min_threshold: float = 0.5) -> 
    None:
        self._min = min_threshold def score( self, *, normalized_company: dict, contacts: 
        list[dict], segment: dict,
    ) -> tuple[float, dict, list[str]]: """Возвращает (score, breakdown, reasons). Пока — просто 1.0 
        если is_relevant.""" return 1.0, {"note": "scorer_stub"}, []
``` **Важно:** в 2C.1 скоринг — заглушка. `is_relevant` из нормализации уже даёт бинарный фильтр. 
Полноценный скоринг по `scoring_weights` — в 2C.3.
### `service.py` — `SearchOrchestrator`
```python import asyncio import time from datetime import datetime, timezone from uuid import UUID 
import structlog from common.context import get_trace_id from common.errors import AppError, 
NotFoundError, ValidationError from sourcing_service.clients.contact_store_client import 
ContactStoreClient from sourcing_service.clients.icp_client import ICPClient, ICPNotFoundError from 
sourcing_service.config import Settings from sourcing_service.connectors.base import RawCandidate, 
SearchCriteria from sourcing_service.connectors.registry import ConnectorRegistry from 
sourcing_service.events import (
    emit_contacts_found, emit_contacts_search_started, emit_contacts_enriched, ) from 
sourcing_service.models import SearchJob, SearchJobItem from 
sourcing_service.normalization.normalizer import Normalizer from sourcing_service.repository import 
SearchJobRepository from sourcing_service.scoring.scorer import Scorer from nats_client.publisher 
import Publisher logger = structlog.get_logger() class SearchOrchestrator:
    def __init__( self, repo: SearchJobRepository, icp_client: ICPClient, contact_store: 
        ContactStoreClient, registry: ConnectorRegistry, normalizer: Normalizer, scorer: Scorer, 
        publisher: Publisher, settings: Settings,
    ) -> None: self._repo = repo self._icp = icp_client self._store = contact_store self._registry = 
        registry self._normalizer = normalizer self._scorer = scorer self._publisher = publisher 
        self._settings = settings
    async def create_and_run( self, *, tenant_id: UUID, icp_id: UUID, segment_id: str, sources: 
        list[str] | None = None, limit_per_source: int | None = None, trace_id: str,
    ) -> SearchJob: """Создаёт job и запускает поиск асинхронно в фоне."""
        # 1. Создаём job
        job = SearchJob( tenant_id=tenant_id, icp_id=icp_id, segment_id=segment_id, brief_id="", # 
            заполним после получения ICP status="pending", params={
                "sources": sources or self._registry.list_available(), "limit_per_source": 
                limit_per_source or self._settings.max_candidates_per_source,
            },
            progress={}, trace_id=trace_id, ) await self._repo.add(job)
        # 2. Публикуем событие
        await emit_contacts_search_started( self._publisher, job, sources=job.params["sources"], 
            trace_id=trace_id,
        )
        # 3. Запускаем в фоне
        asyncio.create_task(self._run_job(job.id, tenant_id=tenant_id, trace_id=trace_id)) return 
        job
    async def _run_job(self, job_id: UUID, *, tenant_id: UUID, trace_id: str) -> None: """Основной 
        пайплайн. Выполняется в фоне.""" from db.session import async_session_factory from db.rls 
        import set_tenant_context started = time.monotonic() async with async_session_factory() as 
        session:
            async with session.begin(): await set_tenant_context(session, tenant_id) repo = 
                SearchJobRepository(session) job = await repo.get(job_id) if job is None:
                    logger.error("search_job_not_found", job_id=str(job_id)) return try: job.status 
                    = "running" job.started_at = datetime.now(timezone.utc) await session.flush()
                    # 1. Получаем ICP
                    icp = await self._icp.get_icp(str(job.icp_id), tenant_id=str(tenant_id), 
                    trace_id=trace_id) job.brief_id = icp.get("brief_id", "") segments = 
                    icp.get("payload", {}).get("segments", []) segment = next((s for s in segments 
                    if s.get("id") == job.segment_id), None) if segment is None:
                        raise AppError(f"Segment {job.segment_id} not found in ICP", 
                        code="segment_not_found", status_code=400)
                    # 2. Собираем criteria из сегмента
                    criteria = self._build_criteria(segment, job.params)
                    # 3. Запускаем коннекторы параллельно
                    sources = job.params.get("sources", []) available = [s for s in sources if s in 
                    self._registry.list_available()] all_candidates: list[RawCandidate] = [] 
                    seen_keys: set[str] = set() total_cost = 0.0 job.progress = {
                        "stage": "sourcing", "sources_done": 0, "sources_total": len(available), 
                        "candidates_raw": 0,
                    }
                    await session.flush() for source_name in available[: 
                    self._settings.max_sources_per_search]:
                        try: connector = self._registry.get(source_name) result = await 
                            connector.search(criteria) total_cost += result.cost_usd for cand in 
                            result.candidates:
                                key = cand.dedup_key() if key in seen_keys: continue 
                                seen_keys.add(key) all_candidates.append(cand)
                        except Exception as e: logger.warning("connector_failed", 
                            source=source_name, error=str(e))
                        job.progress = { **job.progress, "sources_done": 
                            job.progress.get("sources_done", 0) + 1, "candidates_raw": 
                            len(all_candidates),
                        }
                        await session.flush() job.candidates_raw_count = len(all_candidates) 
                    job.progress = {**job.progress, "stage": "normalizing", "candidates_normalized": 
                    0} await session.flush()
                    # 4. Сохраняем raw items
                    items: list[SearchJobItem] = [] for cand in all_candidates: item = 
                        SearchJobItem(
                            tenant_id=tenant_id, job_id=job.id, source=cand.source, 
                            source_url=cand.source_url, raw_payload={
                                "title": cand.title, "snippet": cand.snippet, "domain": cand.domain, 
                                "raw": cand.raw_payload,
                            },
                            status="raw", ) session.add(item) items.append(item) await 
                    session.flush()
                    # 5. Нормализуем батчем
                    segment_context = self._segment_to_context(segment) normalized_results = await 
                    self._normalizer.normalize_batch(
                        all_candidates, tenant_id=tenant_id, segment_context=segment_context, 
                        max_concurrency=self._settings.max_parallel_llm,
                    ) norm_map: dict[str, tuple] = {} for cand, res, err in normalized_results: 
                        norm_map[cand.dedup_key()] = (res, err)
                    # 6. Обновляем items + скорим + persist
                    job.progress = {**job.progress, "stage": "scoring"} await session.flush() 
                    normalized_count = 0 persisted_count = 0 companies_created = 0 companies_merged 
                    = 0 contacts_created = 0 contacts_merged = 0 for item, cand in zip(items, 
                    all_candidates, strict=False):
                        res, err = norm_map.get(cand.dedup_key(), (None, "unknown")) if res is None 
                        or err:
                            item.status = "failed" item.error = err continue if not res.is_company 
                        or not res.is_relevant:
                            item.status = "skipped" item.skip_reason = "not_relevant" if 
                            res.is_company else "not_company" continue
                        normalized_count += 1 item.normalized_company = res.company 
                        item.normalized_contacts = [c.model_dump() for c in res.contacts] 
                        item.status = "normalized"
                        # Скоринг
                        score, breakdown, _ = self._scorer.score( normalized_company=res.company, 
                            contacts=item.normalized_contacts, segment=segment,
                        ) item.score = score item.score_breakdown = breakdown if score < 
                        self._settings.min_score_threshold:
                            item.status = "skipped" item.skip_reason = f"low_score:{score:.2f}" 
                            continue
                        item.status = "scored" job.candidates_normalized_count = normalized_count 
                    job.progress = {
                        **job.progress, "stage": "persisting", "candidates_normalized": 
                        normalized_count, "candidates_persisted": 0,
                    }
                    await session.flush()
                    # 7. Persist в contact-store
                    for item in items: if item.status != "scored": continue if not 
                        item.normalized_company:
                            continue try:
                            # Компания
                            company_payload = self._build_company_payload(item.normalized_company, 
                            item.source_url) company, action = await self._store.upsert_company(
                                tenant_id=str(tenant_id), payload=company_payload, 
                                trace_id=trace_id, 
                                idempotency_key=f"sourcing:{job.id}:company:{item.id}",
                            ) item.company_id = UUID(company["id"]) if company else None if action 
                            == "created":
                                companies_created += 1 else: companies_merged += 1
                            # Контакты
                            contact_ids: list[str] = [] for c in item.normalized_contacts or []: 
                                contact_payload = self._build_contact_payload(c, item.source_url, 
                                company_id=item.company_id) contact, c_action = await 
                                self._store.upsert_contact(
                                    tenant_id=str(tenant_id), payload=contact_payload, 
                                    trace_id=trace_id, 
                                    idempotency_key=f"sourcing:{job.id}:contact:{item.id}:{c.get('full_name')}",
                                ) if contact is None: continue contact_ids.append(contact["id"]) if 
                                c_action == "created":
                                    contacts_created += 1 else: contacts_merged += 1 
                            item.contact_ids = contact_ids item.status = "persisted" persisted_count 
                            += 1 job.progress = {
                                **job.progress, "candidates_persisted": persisted_count,
                            }
                            await session.flush() except Exception as e: 
                            logger.exception("persist_failed", item_id=str(item.id)) item.status = 
                            "failed" item.error = str(e)
                    job.candidates_persisted_count = persisted_count job.companies_created = 
                    companies_created job.companies_merged = companies_merged job.contacts_created = 
                    contacts_created job.contacts_merged = contacts_merged job.total_cost_usd = 
                    total_cost job.duration_ms = int((time.monotonic() - started) * 1000) job.status 
                    = "completed" job.finished_at = datetime.now(timezone.utc) job.progress = 
                    {**job.progress, "stage": "done"} await session.flush()
                    # 8. Событие
                    await emit_contacts_found( self._publisher, job, count=persisted_count, 
                        company_ids=[str(i.company_id) for i in items if i.company_id], 
                        trace_id=trace_id,
                    ) logger.info( "search_job_completed", job_id=str(job.id), 
                        raw=len(all_candidates), normalized=normalized_count, 
                        persisted=persisted_count, companies_created=companies_created, 
                        contacts_created=contacts_created, cost_usd=total_cost, 
                        duration_ms=job.duration_ms,
                    ) except Exception as e: logger.exception("search_job_failed", 
                    job_id=str(job_id)) job.status = "failed" job.error = str(e) job.error_stage = 
                    job.progress.get("stage") job.finished_at = datetime.now(timezone.utc) 
                    job.duration_ms = int((time.monotonic() - started) * 1000) await session.flush()
    def _build_criteria(self, segment: dict, params: dict) -> SearchCriteria: """Превращает сегмент 
        ICP в SearchCriteria.""" firm = segment.get("firmographic", {}) industries = 
        firm.get("industries", []) or [] sub = firm.get("sub_industries", []) or [] geos = 
        firm.get("geos", []) or [] roles = segment.get("roles_to_contact", []) or []
        # Простейшая стратегия: ключевые слова = industry + подсказки
        keywords: list[str] = [] for ind in industries[:3]: keywords.append(ind) for s in sub[:2]: 
            keywords.append(f"{industries[0]} {s}" if industries else s)
        for r in roles[:1]: role_title = r.get("role_title") if role_title and industries: 
                keywords.append(f"{industries[0]} {role_title}")
        if not keywords: keywords = ["компания"] return SearchCriteria( keywords=keywords, geo=geos 
            or ["RU"], language=params.get("language", "ru"), limit=params.get("limit_per_source", 
            50),
        ) def _segment_to_context(self, segment: dict) -> str: """Строка-описание сегмента для 
        промпта.""" parts = [
            f"Название: {segment.get('name', '')}", f"Описание: {segment.get('description', '')}", 
            f"Отрасли: {', '.join(segment.get('firmographic', {}).get('industries', []))}", 
            f"Размер: {', '.join(segment.get('firmographic', {}).get('company_sizes', []))}", f"Гео: 
            {', '.join(segment.get('firmographic', {}).get('geos', []))}",
        ] return "\n".join(p for p in parts if p.split(": ", 1)[1]) def _build_company_payload(self, 
    company: dict, source_url: str | None) -> dict:
        """Конвертирует нормализованную company в payload для contact-store.""" def _fact(v): if 
            isinstance(v, dict):
                return v return {"value": v, "confidence": 0.5, "evidence": []} return { "name": 
            _fact(company.get("name")), "domain": _fact(company.get("domain")), "website": 
            _fact(company.get("website")), "industry": _fact(company.get("industry")), 
            "sub_industry": _fact(company.get("sub_industry")), "locations": 
            company.get("locations") or [],
        }
    def _build_contact_payload(self, contact: dict, source_url: str | None, company_id: UUID | None) 
    -> dict:
        return { "full_name": {"value": contact.get("full_name", ""), "confidence": 
            contact.get("confidence", 0.5), "evidence": []}, "position": {"value": 
            contact.get("position"), "confidence": contact.get("confidence", 0.5), "evidence": []} 
            if contact.get("position") else None, "role_category": contact.get("role_category", 
            "unknown"), "seniority": contact.get("seniority", "unknown"), "emails": 
            contact.get("emails", []), "phones": contact.get("phones", []), "company_id": 
            str(company_id) if company_id else None,
        }
    async def get(self, job_id: UUID) -> SearchJob: job = await self._repo.get(job_id) if job is 
        None:
            raise NotFoundError(f"Search job {job_id} not found") return job async def list(self, *, 
    tenant_id: UUID, status: str | None, limit: int, offset: int) -> list[SearchJob]:
        return await self._repo.list(tenant_id=tenant_id, status=status, limit=limit, offset=offset) 
    async def cancel(self, *, job_id: UUID, tenant_id: UUID, trace_id: str) -> SearchJob:
        job = await self._repo.get(job_id) if job is None: raise NotFoundError(f"Search job {job_id} 
            not found")
        if job.status in ("completed", "failed", "cancelled"): return job job.status = "cancelled" 
        job.finished_at = datetime.now(timezone.utc) await self._repo._s.flush() return job
``` **Важно про `asyncio.create_task`:** job запускается в фоне, но `asyncio.create_task` не 
сохраняет ссылку — GC может убить. Нужно хранить ссылки в `app.state.running_tasks: set`. См. 
main.py.
### `repository.py`
```python class SearchJobRepository: def __init__(self, session: AsyncSession) -> None: self._s = 
        session
    async def get(self, job_id: UUID) -> SearchJob | None: return await self._s.get(SearchJob, 
        job_id)
    async def add(self, job: SearchJob) -> SearchJob: self._s.add(job) await self._s.flush() return 
        job
    async def list(self, *, tenant_id: UUID, status: str | None = None, limit: int = 50, offset: int 
    = 0) -> list[SearchJob]:
        stmt = select(SearchJob).where(SearchJob.tenant_id == tenant_id) if status: stmt = 
            stmt.where(SearchJob.status == status)
        stmt = stmt.order_by(SearchJob.created_at.desc()).limit(limit).offset(offset) return 
        list((await self._s.execute(stmt)).scalars().all())
```
### `schemas.py`
```python class SearchCreateRequest(BaseModel): model_config = ConfigDict(extra="forbid") icp_id: 
    UUID segment_id: str sources: list[str] | None = None limit_per_source: int | None = Field(None, 
    ge=1, le=200)
class SearchJobRead(BaseModel): model_config = ConfigDict(extra="ignore") id: UUID tenant_id: UUID 
    icp_id: UUID segment_id: str brief_id: str status: str params: dict progress: dict 
    candidates_raw_count: int candidates_normalized_count: int candidates_persisted_count: int 
    companies_created: int companies_merged: int contacts_created: int contacts_merged: int 
    total_cost_usd: float duration_ms: int | None error: str | None error_stage: str | None 
    started_at: datetime | None finished_at: datetime | None created_at: datetime updated_at: 
    datetime
class SearchJobSummary(BaseModel): model_config = ConfigDict(extra="ignore") id: UUID icp_id: UUID 
    segment_id: str status: str candidates_raw_count: int candidates_persisted_count: int 
    total_cost_usd: float duration_ms: int | None created_at: datetime
```
### `api/routes.py`
```python @router.post("", response_model=SearchJobRead, status_code=201) async def create_search( 
    data: SearchCreateRequest, svc: SearchOrchestrator = Depends(get_service),
) -> SearchJobRead: tenant_id = get_tenant_id() if tenant_id is None: raise 
        ValidationError("X-Tenant-ID required")
    job = await svc.create_and_run( tenant_id=tenant_id, icp_id=data.icp_id, 
        segment_id=data.segment_id, sources=data.sources, limit_per_source=data.limit_per_source, 
        trace_id=get_trace_id() or "",
    ) return SearchJobRead.model_validate(job, from_attributes=True) @router.get("/{job_id}", 
response_model=SearchJobRead) async def get_search(job_id: UUID, svc: SearchOrchestrator = 
Depends(get_service)) -> SearchJobRead:
    job = await svc.get(job_id) return SearchJobRead.model_validate(job, from_attributes=True) 
@router.get("", response_model=list[SearchJobSummary]) async def list_searches(
    status_filter: str | None = Query(None, alias="status"), limit: int = Query(50, ge=1, le=200), 
    offset: int = Query(0, ge=0), svc: SearchOrchestrator = Depends(get_service),
) -> list[SearchJobSummary]: tenant_id = get_tenant_id() if tenant_id is None: raise 
        ValidationError("X-Tenant-ID required")
    jobs = await svc.list(tenant_id=tenant_id, status=status_filter, limit=limit, offset=offset) 
    return [SearchJobSummary.model_validate(j, from_attributes=True) for j in jobs]
@router.post("/{job_id}/cancel", response_model=SearchJobRead) async def cancel_search(job_id: UUID, 
svc: SearchOrchestrator = Depends(get_service)) -> SearchJobRead:
    tenant_id = get_tenant_id() if tenant_id is None: raise ValidationError("X-Tenant-ID required") 
    job = await svc.cancel(job_id=job_id, tenant_id=tenant_id, trace_id=get_trace_id() or "") return 
    SearchJobRead.model_validate(job, from_attributes=True)
```
### `main.py` — обновить
```python
# в lifespan:
app.state.icp_client = ICPClient(settings.icp_service_url) app.state.contact_store = 
ContactStoreClient(settings.contact_store_url) app.state.llm = LLMClient(settings) 
app.state.normalizer = Normalizer(app.state.llm) app.state.scorer = 
Scorer(min_threshold=settings.min_score_threshold) app.state.connector_registry = registry 
app.state.running_tasks = set() # для хранения ссылок на background tasks
# при shutdown:
for task in app.state.running_tasks: task.cancel() await app.state.icp_client.close() await 
app.state.contact_store.close() await app.state.llm.close() await registry.close_all() ``` **Важно 
про `asyncio.create_task` и GC:** сохранять ссылку: ```python task = 
asyncio.create_task(self._run_job(...)) self._running_tasks.add(task) 
task.add_done_callback(self._running_tasks.discard) ``` Передать `running_tasks` в 
`SearchOrchestrator` через конструктор.
### Тесты + E2E
`tests/test_e2e.py` — с respx на ICP, contact-store, LLM, Serper. Проверить: 1. `POST /searches` → 
201. 2. Дождаться `status=completed` (poll через GET). 3. Проверить `candidates_persisted_count > 
0`. 4. Проверить, что в contact-store пришли upsert-запросы.
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/ -v --cov=sourcing_service 
--cov-report=term-missing
# Ожидание: coverage >= 80% (sourcing сложный, 90% может быть недостижимо)
uv run mypy services/sourcing-service uv run ruff check services/sourcing-service
# E2E на dev
export TENANT="<sandbox>" export BASE="https://sourcing.dev.aitler.ru" export 
ICP_ID="<реальный_icp_id>" export SEGMENT_ID="<реальный_segment_id_из_icp>" JOB=$(curl -sX POST 
$BASE/searches \
  -H "Content-Type: application/json" \ -H "X-Tenant-ID: $TENANT" \ -H "Idempotency-Key: e2e-s1" \ 
  -d '{"icp_id": "'$ICP_ID'", "segment_id": "'$SEGMENT_ID'", "sources": ["serper"], 
  "limit_per_source": 10}')
JOB_ID=$(echo $JOB | jq -r .id) echo "Job: $JOB_ID"
# Ждём завершения
for i in $(seq 1 30); do sleep 3 STATUS=$(curl -s -H "X-Tenant-ID: $TENANT" $BASE/searches/$JOB_ID | 
  jq -r .status) echo "iter $i: $STATUS" [ "$STATUS" = "completed" ] && break [ "$STATUS" = "failed" 
  ] && break
done
# Финальный статус
curl -s -H "X-Tenant-ID: $TENANT" $BASE/searches/$JOB_ID | jq '{status, candidates_raw_count, 
candidates_normalized_count, candidates_persisted_count, companies_created, contacts_created, 
total_cost_usd, duration_ms}'
# Ожидание: completed, persisted >= 1 В contact-store появились компании
curl -s -H "X-Tenant-ID: $TENANT" https://contact-store.dev.aitler.ru/companies?limit=100 | jq 
'length'
# Ожидание: >= companies_created Событие в NATS
bash scripts/nats-cli.sh stream view CONTACTS --last 10 | grep -E "contacts\.(search_started|found)"
# Ожидание: оба типа
```
## Подсказки
- **`asyncio.create_task` + `_running_tasks`** — обязательно, иначе GC убьёт задачу. - **Фоновая 
задача открывает свою session** — она не может переиспользовать session из request'а. - 
**`strict=False` в `zip`** — на случай, если длины не совпадут (не должны, но страховка). - 
**Idempotency-Key для contact-store** — `f"sourcing:{job.id}:company:{item.id}"`. При retry — тот же 
ключ, дубликатов не будет. - **Scorer пока заглушка** — вернёт 1.0. Полноценный скоринг в 2C.3.
## Анти-паттерны
- ❌ Не запускать фоновую задачу без сохранения ссылки. - ❌ Не переиспользовать session из 
request'а в фоне. - ❌ Не забывать `Idempotency-Key` при вызовах contact-store. - ❌ Не позволять 
job висеть в running вечно — добавить timeout (позже, в 2C.3). ---
# 2C.2 — Остальные коннекторы
---
# Задача 2C.2.1 — `WebsiteParserConnector` (Playwright)
**Файл:** `docs/tasks/sprint-2c/2c.2.1-website-parser.md`
## Цель
Коннектор, который по домену/URL загружает страницы сайта компании и извлекает текст (для 
последующей нормализации через LLM). Использует Playwright для JS-рендеринга.
## Зависимости
2C.1.5.
## Что создать
- `connectors/website_parser.py` - Обновить `pyproject.toml` — добавить Playwright. - Обновить 
`Dockerfile` — установить браузеры. - Тесты.
## Детали
### `pyproject.toml`
Добавить: ```toml "playwright>=1.48", "beautifulsoup4>=4.12", "lxml>=5.3", "tldextract>=5.1", ```
### `Dockerfile` — обновить
```dockerfile
# ... после uv sync
RUN uv run playwright install --with-deps chromium ``` **Важно:** образ станет больше (~500 МБ 
дополнительно). Это цена за JS-рендеринг. Если не нужен JS — можно обойтись httpx + bs4, но многие 
сайты без JS не отдают контент. **Альтернатива:** сделать Playwright опциональным — рендерить только 
если httpx вернул «пустой» HTML (< 500 символов текста). Это экономит время и ресурсы. **Решение:** 
делаем гибрид: 1. Сначала httpx + bs4. 2. Если текста < 500 символов — Playwright.
### `connectors/website_parser.py`
```python import asyncio import time from dataclasses import dataclass import httpx import structlog 
from bs4 import BeautifulSoup from sourcing_service.connectors.base import (
    Connector, ConnectorResult, RawCandidate, SearchCriteria, ) from 
sourcing_service.connectors.exceptions import ConnectorUnavailableError logger = 
structlog.get_logger() @dataclass class ParsedPage:
    url: str title: str text: str meta_description: str emails: list[str] phones: list[str] class 
WebsiteParserConnector(Connector):
    """Загружает страницы сайтов и извлекает текст + контакты. НЕ ищет сайты — работает по списку 
    домен/URL из criteria.extra['urls']. Используется как «обогатитель» после WebSearchConnector. 
    """ name = "website_parser" def __init__(self, *, timeout: float = 20.0, max_pages_per_site: int 
    = 3) -> None:
        super().__init__(rate_limit_per_sec=2.0) self._timeout = timeout self._max_pages = 
        max_pages_per_site self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5.0), headers={"User-Agent": "Mozilla/5.0 
            (compatible; OutreachOS/0.1; +https://aitler.ru)"}, follow_redirects=True,
        ) self._playwright_available = False @property def is_available(self) -> bool: return True # 
        httpx всегда доступен
    async def search(self, criteria: SearchCriteria) -> ConnectorResult: """Для этого коннектора 
        «поиск» = парсинг переданных URL.""" urls = criteria.extra.get("urls", []) if not urls:
            return ConnectorResult(source=self.name, candidates=[], error="no urls in 
            criteria.extra")
        started = time.monotonic() candidates: list[RawCandidate] = [] for url in urls[:20]: # 
        ограничиваем
            try: page = await self._parse(url) if page is None: continue 
                candidates.append(RawCandidate(
                    source=self.name, source_url=page.url, title=page.title, 
                    snippet=page.meta_description or page.text[:300], 
                    domain=self._extract_domain(page.url), raw_payload={
                        "text": page.text[:15000], # ограничиваем "emails": page.emails, "phones": 
                        page.phones, "meta_description": page.meta_description,
                    },
                )) except Exception as e: logger.warning("parse_failed", url=url, error=str(e)) 
        duration_ms = int((time.monotonic() - started) * 1000) return ConnectorResult(
            source=self.name, candidates=candidates, cost_usd=0.0, # бесплатно (кроме CPU) 
            duration_ms=duration_ms,
        ) async def _parse(self, url: str) -> ParsedPage | None:
        # 1. Пробуем httpx
        try: resp = await self._client.get(url) resp.raise_for_status() html = resp.text final_url = 
            str(resp.url)
        except Exception as e: logger.debug("httpx_parse_failed", url=url, error=str(e)) return None 
        soup = BeautifulSoup(html, "lxml") text = self._extract_text(soup)
        # 2. Если мало текста — пробуем Playwright
        if len(text) < 500 and self._playwright_available: text_js, html_js = await 
            self._render_with_playwright(final_url) if len(text_js) > len(text):
                text = text_js soup = BeautifulSoup(html_js, "lxml") if not text: return None title 
        = soup.title.string.strip() if soup.title and soup.title.string else "" meta = 
        soup.find("meta", attrs={"name": "description"}) meta_description = meta["content"].strip() 
        if meta and meta.get("content") else "" return ParsedPage(
            url=final_url, title=title, text=text, meta_description=meta_description, 
            emails=self._extract_emails(html), phones=self._extract_phones(html),
        ) def _extract_text(self, soup: BeautifulSoup) -> str: for tag in soup(["script", "style", 
        "noscript", "header", "footer", "nav"]):
            tag.decompose() text = soup.get_text(separator="\n", strip=True)
        # Схлопываем пустые строки
        lines = [line for line in text.split("\n") if line.strip()] return "\n".join(lines) def 
    _extract_emails(self, html: str) -> list[str]:
        import re pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" found = 
        set(re.findall(pattern, html))
        # Фильтруем мусор
        return [e.lower() for e in found if not any(x in e for x in ["example.", "test.", "sentry", 
        "noreply", "no-reply"])][:10]
    def _extract_phones(self, html: str) -> list[str]: import re
        # Простой паттерн для РФ: +7 или 8 + 10 цифр
        pattern = r"(?:\+7|8)[\s\-\(\)]?\d{3}[\s\-\(\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}" found = 
        set(re.findall(pattern, html)) return list(found)[:10]
    async def _render_with_playwright(self, url: str) -> tuple[str, str]: """Fallback на Playwright, 
        если httpx вернул мало текста.""" try:
            from playwright.async_api import async_playwright except ImportError: return "", "" try: 
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True) context = await 
                browser.new_context(
                    user_agent="Mozilla/5.0 (compatible; OutreachOS/0.1)", viewport={"width": 1280, 
                    "height": 800},
                ) page = await context.new_page() await page.goto(url, timeout=self._timeout * 1000, 
                wait_until="domcontentloaded") await page.wait_for_timeout(2000) html = await 
                page.content() text = await page.inner_text("body") await browser.close() return 
                text, html
        except Exception as e: logger.warning("playwright_failed", url=url, error=str(e)) return "", 
            ""
    @staticmethod def _extract_domain(url: str) -> str | None: if not url: return None import 
        tldextract ext = tldextract.extract(url) if not ext.domain or not ext.suffix:
            return None return f"{ext.domain}.{ext.suffix}".lower() async def close(self) -> None: 
        await self._client.aclose()
```
### Когда использовать
Этот коннектор **не ищет** сайты. Он **парсит** переданные URL. Использование: 1. После 
`WebSearchConnector` — оркестратор берёт топ-URL из `WebSearchResult` и передаёт их в 
`criteria.extra["urls"]` для `website_parser`. 2. Или самостоятельно — если у нас есть список URL из 
другого источника (например, вручную). **Интеграция в `SearchOrchestrator`:** после этапа `sourcing` 
— если `website_parser` в `sources`, оркестратор берёт URL из уже найденных кандидатов и парсит их. 
Это **не отдельный источник**, а «обогатитель». **Решение:** вынести в отдельный шаг в `_run_job`: 
```python
# 3.5. Обогащение парсером (если включён)
if "website_parser" in sources: urls_to_parse = [c.source_url for c in all_candidates if 
    c.source_url][:20] criteria_parse = SearchCriteria(keywords=[], extra={"urls": urls_to_parse}) 
    parser = self._registry.get("website_parser") parse_result = await parser.search(criteria_parse)
    # Merge по домену: если есть уже кандидат с тем же доменом — дополняем raw_payload
    ... ``` Детали — на усмотрение агента-разработчика, но принцип: parser дополняет кандидатов от 
search-коннекторов.
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/test_website_parser.py -v
# E2E
docker compose ... exec -T sourcing-service python - <<'PY' import asyncio from 
sourcing_service.connectors.base import SearchCriteria from 
sourcing_service.connectors.website_parser import WebsiteParserConnector async def main():
    c = WebsiteParserConnector() criteria = SearchCriteria(keywords=[], extra={"urls": 
    ["https://example.com"]}) result = await c.search(criteria) for cand in result.candidates:
        print(f"{cand.domain}: {len(cand.raw_payload.get('text', ''))} chars, 
        emails={cand.raw_payload.get('emails')}")
    await c.close() asyncio.run(main()) PY
# Ожидание: домен + текст + возможно emails
```
## Подсказки
- **Playwright опционален** — не запускать, если httpx дал достаточно текста. - **Ограничение на 
текст** — `text[:15000]` в raw_payload. Иначе БД распухнет. - **Email/phone regex** — простые. Для 
сложных случаев — отдельный enrichment-сервис. - **User-Agent** — указывать реальный, иначе многие 
сайты блокируют.
## Анти-паттерны
- ❌ Не рендерить через Playwright всё подряд — только если httpx не справился. - ❌ Не хранить 
полный HTML в raw_payload — только текст. - ❌ Не парсить больше 20 URL за раз. ---
# Задача 2C.2.2 — `RegistryConnector` (Rusprofile / ЕГРЮЛ)
**Файл:** `docs/tasks/sprint-2c/2c.2.2-registry.md`
## Цель
Коннектор к реестрам РФ: Rusprofile (или аналог). По названию компании или ИНН достаёт: юр. 
название, ИНН, ОГРН, адрес, руководителя, ОКВЭД, размер.
## Зависимости
2C.1.5.
## Что создать
- `connectors/rusprofile.py` (или `registry.py`) - Тесты.
## Детали
### Проблема
У Rusprofile **нет публичного API**. Варианты: 1. **Парсинг HTML Rusprofile.** Хрупко (сайт может 
менять разметку), но бесплатно. 2. **DaData API** — платный, но надёжный. 
`https://dadata.ru/api/find-party/`. ~0.5 копейки за запрос. 3. **ЕГРЮЛ API** (ФНС) — с 2022 закрыт 
для публичного доступа. 4. **Checko.ru** — есть API (платный). 5. **Rusprofile API** — есть платный 
тариф для юрлиц. **Решение:** делаем коннектор с **абстракцией провайдера**: - 
`DaDataRegistryProvider` — по умолчанию (надёжно, недорого). - `RusprofileParserProvider` — fallback 
(парсинг HTML).
### `connectors/registry.py`
```python from abc import ABC, abstractmethod import time import httpx import structlog from 
sourcing_service.connectors.base import (
    Connector, ConnectorResult, RawCandidate, SearchCriteria, ) from 
sourcing_service.connectors.exceptions import ConnectorUnavailableError logger = 
structlog.get_logger() class RegistryProvider(ABC):
    name: str @abstractmethod async def search_by_query(self, query: str, *, limit: int = 10) -> 
    list[dict]: ... @abstractmethod async def search_by_inn(self, inn: str) -> dict | None: ... 
    async def close(self) -> None:
        return None class DaDataProvider(RegistryProvider): """DaData — надёжный, платный (~0.5 
    копейки за запрос). Docs: https://dadata.ru/api/find-party/ """ name = "dadata" def 
    __init__(self, api_key: str, secret_key: str) -> None:
        self._api_key = api_key self._secret = secret_key self._client = httpx.AsyncClient( 
            base_url="https://suggestions.dadata.ru/suggestions/api/4_1/rs", headers={
                "Content-Type": "application/json", "Accept": "application/json", "Authorization": 
                f"Token {api_key}", "X-Secret": secret_key,
            },
            timeout=httpx.Timeout(20.0, connect=5.0), ) @property def is_available(self) -> bool: 
        return bool(self._api_key and self._secret)
    async def search_by_query(self, query: str, *, limit: int = 10) -> list[dict]: resp = await 
        self._client.post(
            "/findById/party", json={"query": query, "count": limit}, ) resp.raise_for_status() 
        return resp.json().get("suggestions", [])
    async def search_by_inn(self, inn: str) -> dict | None: results = await 
        self.search_by_query(inn, limit=1) return results[0] if results else None
    async def close(self) -> None: await self._client.aclose() class RegistryConnector(Connector): 
    """Поиск компаний в реестрах (РФ). Использует переданный провайдер. По умолчанию — DaData. """ 
    name = "registry" def __init__(self, provider: RegistryProvider, *, cost_per_call_usd: float = 
    0.00005) -> None:
        super().__init__(rate_limit_per_sec=5.0) self._provider = provider self._cost = 
        cost_per_call_usd
    @property def is_available(self) -> bool: return getattr(self._provider, "is_available", True) 
    @property def cost_per_call_usd(self) -> float:
        return self._cost async def search(self, criteria: SearchCriteria) -> ConnectorResult: 
        """Ищет компании в реестре по ключевым словам из criteria.""" started = time.monotonic() 
        candidates: list[RawCandidate] = [] errors: list[str] = [] queries = criteria.keywords[:3] 
        for q in queries:
            try: results = await self._provider.search_by_query(q, limit=criteria.limit) for item in 
                results:
                    data = item.get("data", {}) name = data.get("name", {}).get("short_with_opf") or 
                    data.get("name", {}).get("full_with_opf") inn = data.get("inn") ogrn = 
                    data.get("ogrn") address = data.get("address", {}).get("value") management = 
                    data.get("management") or {} manager_name = management.get("name") manager_post 
                    = management.get("post") okved = data.get("okved") employee_count = 
                    data.get("employee_count") status = data.get("state", {}).get("status") if not 
                    name:
                        continue
                    # Пропускаем ликвидированные
                    if status and status != "ACTIVE": continue candidates.append(RawCandidate( 
                        source=self.name, source_url=None, title=name, snippet=f"ИНН {inn}, {address 
                        or ''}".strip(", "), domain=None, raw_payload={
                            "name": name, "inn": inn, "ogrn": ogrn, "address": address, 
                            "manager_name": manager_name, "manager_post": manager_post, "okved": 
                            okved, "employee_count": employee_count, "status": status, "source": 
                            self._provider.name,
                        },
                    )) except Exception as e: logger.warning("registry_query_failed", query=q, 
                error=str(e)) errors.append(f"{q}: {e}")
        duration_ms = int((time.monotonic() - started) * 1000) return ConnectorResult( 
            source=self.name, candidates=candidates, cost_usd=self._cost * len(queries), error="; 
            ".join(errors) if errors else None, duration_ms=duration_ms,
        ) async def close(self) -> None: await self._provider.close() ``` **Важно:** `RawCandidate` 
от реестра не имеет `domain` и `source_url`. Дедуп по `title`. Нормализатор должен понять, что это 
компания, и создать карточку с ИНН/ОГРН. **Проблема:** в `Normalizer` промпт ожидает URL. Для 
реестра — передаём `raw_payload` как `candidate_extra`. Нужно доработать промпт — добавить поле 
«дополнительные данные от источника». **Обновить `build_normalize_prompt`:** ```python def 
build_normalize_prompt(
    *, candidate_title: str | None, candidate_snippet: str | None, candidate_url: str | None, 
    candidate_domain: str | None, segment_context: str, candidate_extra: str | None = None,
) -> Prompt:
    # ... в промпте уже есть {f'- Дополнительно: {candidate_extra}' if candidate_extra else ''}
``` И в `SearchOrchestrator._build_criteria` / нормализации — передавать 
`candidate_extra=json.dumps(cand.raw_payload, ensure_ascii=False)` для registry-кандидатов. 
**Интеграция в `_run_job`:** В цикле нормализации: ```python normalized_results = await 
self._normalizer.normalize_batch(
    all_candidates, tenant_id=tenant_id, segment_context=segment_context, 
    max_concurrency=self._settings.max_parallel_llm,
) ``` А `Normalizer.normalize` вызывает `build_normalize_prompt` без `candidate_extra`. Нужно 
расширить `Normalizer`, чтобы он передавал `candidate.raw_payload` если `source` в `("registry",)`. 
```python
# в Normalizer.normalize:
extra = None if candidate.source in ("registry",): extra = json.dumps(candidate.raw_payload, 
    ensure_ascii=False, indent=2)[:2000]
prompt = build_normalize_prompt( ..., candidate_extra=extra, ) ``` И в промпте добавить инструкцию: 
«Если есть ИНН/ОГРН — используй их для company.registry_ids».
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/test_registry.py -v
# E2E с реальным DaData
docker compose ... exec -T sourcing-service python - <<'PY' import asyncio from 
sourcing_service.connectors.base import SearchCriteria from sourcing_service.connectors.registry 
import DaDataProvider, RegistryConnector async def main():
    provider = DaDataProvider(api_key="...", secret_key="...") c = RegistryConnector(provider) 
    criteria = SearchCriteria(keywords=["Сбербанк"], limit=5) result = await c.search(criteria) for 
    cand in result.candidates:
        print(cand.title, cand.raw_payload.get("inn")) await c.close() asyncio.run(main()) PY
# Ожидание: список компаний с ИНН
```
## Подсказки
- **DaData** — 10 000 запросов/день бесплатно, потом платно. Для старта хватит. - **Проверять 
`state.status == "ACTIVE"`** — не тратить время на ликвидированные. - **`okved`** — можно 
использовать для скоринга по отрасли.
## Анти-паттерны
- ❌ Не парсить Rusprofile HTML напрямую — хрупко. Использовать API провайдеров. - ❌ Не забывать 
про rate limit DaData (по умолчанию 10 req/sec). - ❌ Не хранить весь ответ DaData в raw_payload — 
только нужные поля. ---
# Задача 2C.2.3 — `EnricherConnector` (email/phone enrichment)
**Файл:** `docs/tasks/sprint-2c/2c.2.3-enricher.md`
## Цель
Обогатитель: по домену компании и ФИО контакта достаёт email и/или phone. Провайдеры: Hunter.io, 
Snov.io.
## Зависимости
2C.1.5.
## Детали
### Когда использовать
**Это НЕ источник компаний.** Это обогатитель для уже найденных контактов. Вызывается после 
нормализации, если у контакта нет email/phone. **Решение:** вынести в отдельный шаг после 
нормализации в `_run_job`.
### `connectors/enricher.py`
```python from abc import ABC, abstractmethod import time import httpx import structlog from 
sourcing_service.connectors.base import Connector, ConnectorResult, RawCandidate, SearchCriteria 
from sourcing_service.connectors.exceptions import ConnectorUnavailableError logger = 
structlog.get_logger() class EnricherProvider(ABC):
    name: str @abstractmethod async def find_email(self, *, domain: str, first_name: str | None, 
    last_name: str | None) -> dict | None: ... @abstractmethod async def domain_emails(self, *, 
    domain: str, limit: int = 10) -> list[dict]: ... async def close(self) -> None:
        return None class HunterProvider(EnricherProvider): """Hunter.io — email finder + domain 
    search. Docs: https://hunter.io/api-documentation Cost: ~$0.02 per email found (зависит от 
    тарифа). """ name = "hunter" def __init__(self, api_key: str) -> None:
        self._api_key = api_key self._client = httpx.AsyncClient( 
            base_url="https://api.hunter.io/v2", timeout=httpx.Timeout(20.0, connect=5.0),
        ) @property def is_available(self) -> bool: return bool(self._api_key) async def 
    find_email(self, *, domain: str, first_name: str | None, last_name: str | None) -> dict | None:
        if not first_name or not last_name: return None resp = await self._client.get( 
            "/email-finder", params={
                "domain": domain, "first_name": first_name, "last_name": last_name, "api_key": 
                self._api_key,
            },
        ) if resp.status_code == 404: return None resp.raise_for_status() return 
        resp.json().get("data")
    async def domain_emails(self, *, domain: str, limit: int = 10) -> list[dict]: resp = await 
        self._client.get(
            "/domain-search", params={"domain": domain, "limit": limit, "api_key": self._api_key}, ) 
        if resp.status_code == 404:
            return [] resp.raise_for_status() return resp.json().get("data", {}).get("emails", []) 
    async def close(self) -> None:
        await self._client.aclose() class EnricherConnector(Connector): """Обогатитель контактов: 
    email/phone. НЕ ищет компании. Работает по переданным контактам в criteria.extra['contacts']. 
    """ name = "enricher" def __init__(self, provider: EnricherProvider, *, cost_per_email_usd: 
    float = 0.02) -> None:
        super().__init__(rate_limit_per_sec=3.0) self._provider = provider self._cost = 
        cost_per_email_usd
    @property def is_available(self) -> bool: return getattr(self._provider, "is_available", True) 
    async def search(self, criteria: SearchCriteria) -> ConnectorResult:
        """Обогащает контакты из criteria.extra['contacts']. Возвращает RawCandidate с заполненными 
        emails/phones в raw_payload. """ started = time.monotonic() contacts = 
        criteria.extra.get("contacts", []) candidates: list[RawCandidate] = [] cost = 0.0 for c in 
        contacts:
            domain = c.get("company_domain") if not domain: continue try: found = await 
                self._provider.find_email(
                    domain=domain, first_name=c.get("first_name"), last_name=c.get("last_name"), ) 
                if found and found.get("email"):
                    cost += self._cost candidates.append(RawCandidate( source=self.name, 
                        source_url=None, title=c.get("full_name"), snippet=found.get("email"), 
                        domain=domain, raw_payload={
                            "contact_full_name": c.get("full_name"), "email": found.get("email"), 
                            "confidence": found.get("confidence", 50) / 100.0, "source": 
                            self._provider.name,
                        },
                    )) except Exception as e: logger.warning("enrich_failed", domain=domain, 
                error=str(e))
        duration_ms = int((time.monotonic() - started) * 1000) return ConnectorResult( 
            source=self.name, candidates=candidates, cost_usd=cost, duration_ms=duration_ms,
        ) async def close(self) -> None: await self._provider.close() ```
### Интеграция в `_run_job`
**Это отдельный шаг ПОСЛЕ нормализации:** ```python
# 5.5. Обогащение контактов (если включено)
if "enricher" in sources: contacts_to_enrich = [] for item in items: if item.status != "scored" or 
        not item.normalized_contacts:
            continue for c in item.normalized_contacts: if not c.get("emails"): # только если email 
            неизвестен
                contacts_to_enrich.append({ "company_domain": item.normalized_company.get("domain", 
                    {}).get("value") if item.normalized_company else None, "full_name": 
                    c.get("full_name"), "first_name": c.get("full_name", "").split()[0] if 
                    c.get("full_name") else None, "last_name": c.get("full_name", "").split()[-1] if 
                    c.get("full_name") else None,
                })
    if contacts_to_enrich: enricher = self._registry.get("enricher") enrich_criteria = 
        SearchCriteria(keywords=[], extra={"contacts": contacts_to_enrich[:50]}) enrich_result = 
        await enricher.search(enrich_criteria) total_cost += enrich_result.cost_usd
        # Merge по full_name в items
        for cand in enrich_result.candidates: for item in items: for c in item.normalized_contacts 
                or []:
                    if c.get("full_name") == cand.raw_payload.get("contact_full_name"): 
                        c.setdefault("emails", []).append({
                            "value": cand.raw_payload["email"], "type": "work", "is_primary": True, 
                            "confidence": cand.raw_payload.get("confidence", 0.5), "evidence": 
                            [{"source_url": None, "source_type": "enricher", "snippet": None}],
                        })
        await session.flush() ``` **Событие `contacts.enriched`** — публикуется после обогащения.
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/test_enricher.py -v
# E2E с реальным Hunter (если ключ) Ожидание: email найден для контакта
```
## Подсказки
- **Enricher — опциональный.** Если нет ключа Hunter — просто не регистрируем коннектор. - **Не 
обогащать всё подряд.** Только те контакты, у которых нет email. - **Стоимость.** Hunter ~$0.02 за 
email. На 1000 контактов — $20. Учитывать в `total_cost_usd`.
## Анти-паттерны
- ❌ Не обогащать контакты, у которых уже есть email. - ❌ Не запускать enricher без rate limit. - 
❌ Не забывать про cost tracking. ---
# 2C.3 — Скоринг + оркестрация + аналитика
---
# Задача 2C.3.1 — Полноценный `Scorer`
**Файл:** `docs/tasks/sprint-2c/2c.3.1-scorer.md`
## Цель
Заменить заглушку на полноценный скоринг по `scoring_weights` сегмента ICP. Разбить score на 
компоненты, обосновать.
## Зависимости
2C.1.5.
## Что создать
- `scoring/scorer.py` — полностью переписать. - `scoring/features.py` — извлечение фич из 
Company/Contact/ICP. - Тесты.
## Детали
### `features.py`
```python from dataclasses import dataclass @dataclass class SegmentFeatures: """Целевые 
    характеристики сегмента (из ICP).""" industries: list[str] sub_industries: list[str] 
    company_sizes: list[str] # ["smb", "mid", "enterprise"] employee_count_min: int | None 
    employee_count_max: int | None geos: list[str] company_types: list[str] uses_technologies: 
    list[str] does_not_use_technologies: list[str] pain_keywords: list[str] # из pain_hypotheses 
    trigger_keywords: list[str] # из trigger_events target_roles: list[str] # из roles_to_contact
@dataclass class CompanyFeatures: """Характеристики компании (из нормализованной).""" industry: str 
    | None
    sub_industry: str | None employee_count: int | None employee_range: str # 
    smb/mid/enterprise/unknown country: str | None company_type: str | None tech_stack: list[str] 
    signals: list[dict] text_blob: str # весь текст для keyword matching
@dataclass class ContactFeatures: """Характеристики контактов.""" roles: list[str] role_categories: 
    list[str] seniority_levels: list[str]
def extract_segment_features(segment: dict) -> SegmentFeatures: firm = segment.get("firmographic", 
    {}) or {} tech = segment.get("technographic", {}) or {} pains = segment.get("pain_hypotheses", 
    []) or [] triggers = segment.get("trigger_events", []) or [] roles = 
    segment.get("roles_to_contact", []) or [] return SegmentFeatures(
        industries=[i.lower() for i in (firm.get("industries") or [])], sub_industries=[i.lower() 
        for i in (firm.get("sub_industries") or [])], company_sizes=[s.lower() for s in 
        (firm.get("company_sizes") or [])], employee_count_min=firm.get("employee_count_min"), 
        employee_count_max=firm.get("employee_count_max"), geos=[g.upper() for g in 
        (firm.get("geos") or [])], company_types=[t.lower() for t in (firm.get("company_types") or 
        [])], uses_technologies=[t.lower() for t in (tech.get("uses_technologies") or [])], 
        does_not_use_technologies=[t.lower() for t in (tech.get("does_not_use_technologies") or 
        [])], pain_keywords=[(p.get("pain") or "").lower() for p in pains if p.get("pain")], 
        trigger_keywords=[(t.get("trigger") or "").lower() for t in triggers if t.get("trigger")], 
        target_roles=[(r.get("role_title") or "").lower() for r in roles if r.get("role_title")],
    ) def extract_company_features(company: dict) -> CompanyFeatures: def _val(field: str) -> str | 
    None:
        v = company.get(field) if isinstance(v, dict): return v.get("value") return v size = 
    company.get("size_estimate") or {} emp_count = size.get("employee_count") if 
    isinstance(emp_count, dict):
        emp_count = emp_count.get("value") locations = company.get("locations") or [] country = None 
    for loc in locations:
        c = loc.get("country") if isinstance(c, dict): c = c.get("value") if c: country = c break 
    tech = company.get("tech_stack") or [] tech_values = [t.get("value", "").lower() for t in tech 
    if isinstance(t, dict) and t.get("value")] signals = company.get("signals") or []
    # Текстовый блок для keyword matching
    text_parts = [ str(_val("name") or ""), str(_val("industry") or ""), str(_val("sub_industry") or 
        ""), " ".join(str(s.get("summary", "")) for s in signals),
    ] text_blob = " ".join(text_parts).lower() return CompanyFeatures( industry=(_val("industry") or 
        "").lower() or None, sub_industry=(_val("sub_industry") or "").lower() or None, 
        employee_count=emp_count, employee_range=(size.get("employee_range") or "unknown").lower(), 
        country=country, company_type=None, # заполнится из LLM-нормализации, если было 
        tech_stack=tech_values, signals=signals, text_blob=text_blob,
    ) def extract_contact_features(contacts: list[dict]) -> ContactFeatures: roles: list[str] = [] 
    categories: list[str] = [] seniorities: list[str] = [] for c in contacts:
        pos = c.get("position") if isinstance(pos, dict): pos = pos.get("value") if pos: 
            roles.append(pos.lower())
        if c.get("role_category"): categories.append(c["role_category"]) if c.get("seniority"): 
            seniorities.append(c["seniority"])
    return ContactFeatures(roles=roles, role_categories=categories, seniority_levels=seniorities) 
```
### `scorer.py`
```python from dataclasses import dataclass from sourcing_service.scoring.features import ( 
    CompanyFeatures, ContactFeatures, SegmentFeatures, extract_company_features, 
    extract_contact_features, extract_segment_features,
) @dataclass class ScoreResult: total: float breakdown: dict[str, float] reasons: list[str] class 
Scorer:
    """Скорит компанию+контакты по весам ICP-сегмента.""" def __init__(self, *, min_threshold: float 
    = 0.5) -> None:
        self._min = min_threshold def score( self, *, normalized_company: dict, contacts: 
        list[dict], segment: dict,
    ) -> tuple[float, dict, list[str]]: seg = extract_segment_features(segment) comp = 
        extract_company_features(normalized_company) cont = extract_contact_features(contacts) 
        weights = segment.get("scoring_weights") or {} reasons: list[str] = [] breakdown: dict[str, 
        float] = {} breakdown["industry_match"] = self._industry_match(seg, comp, reasons) 
        breakdown["size_match"] = self._size_match(seg, comp, reasons) breakdown["geo_match"] = 
        self._geo_match(seg, comp, reasons) breakdown["pain_match"] = self._pain_match(seg, comp, 
        reasons) breakdown["trigger_match"] = self._trigger_match(seg, comp, reasons) 
        breakdown["role_match"] = self._role_match(seg, cont, reasons) total = 0.0 for key, val in 
        breakdown.items():
            w = float(weights.get(key, 0.0)) total += w * val total = round(min(max(total, 0.0), 
        1.0), 4) return total, breakdown, reasons
    def _industry_match(self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]) -> 
    float:
        if not seg.industries: return 0.5 # нет данных — нейтрально if not comp.industry: return 0.0 
        if comp.industry in seg.industries:
            reasons.append(f"industry exact: {comp.industry}") return 1.0
        # Частичное совпадение
        for ind in seg.industries: if ind in comp.industry or comp.industry in ind: 
                reasons.append(f"industry partial: {comp.industry} ~ {ind}") return 0.7
        # По подотраслям
        if comp.sub_industry and comp.sub_industry in seg.sub_industries: 
            reasons.append(f"sub_industry match: {comp.sub_industry}") return 0.8
        return 0.0 def _size_match(self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: 
    list[str]) -> float:
        if not seg.company_sizes and seg.employee_count_min is None: return 0.5
        # По диапазону сотрудников
        if comp.employee_count is not None: if seg.employee_count_min is not None and 
            comp.employee_count < seg.employee_count_min:
                return 0.0 if seg.employee_count_max is not None and comp.employee_count > 
            seg.employee_count_max:
                return 0.0 reasons.append(f"employee_count in range: {comp.employee_count}") return 
            1.0
        # По диапазону
        if comp.employee_range != "unknown" and comp.employee_range in seg.company_sizes: 
            reasons.append(f"size range match: {comp.employee_range}") return 1.0
        return 0.0 def _geo_match(self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: 
    list[str]) -> float:
        if not seg.geos: return 0.5 if not comp.country: return 0.3 if comp.country.upper() in 
        seg.geos:
            reasons.append(f"geo match: {comp.country}") return 1.0 return 0.0 def _pain_match(self, 
    seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]) -> float:
        if not seg.pain_keywords: return 0.5 blob = comp.text_blob hits = sum(1 for kw in 
        seg.pain_keywords if kw and kw in blob) if hits == 0:
            return 0.0 score = min(hits / len(seg.pain_keywords), 1.0) reasons.append(f"pain 
        keywords matched: {hits}/{len(seg.pain_keywords)}") return round(score, 4)
    def _trigger_match(self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]) -> 
    float:
        if not seg.trigger_keywords: return 0.5 if not comp.signals: return 0.0 signal_text = " 
        ".join(str(s.get("summary", "")) for s in comp.signals).lower() hits = sum(1 for kw in 
        seg.trigger_keywords if kw and kw in signal_text) if hits == 0:
            return 0.0 score = min(hits / len(seg.trigger_keywords), 1.0) reasons.append(f"triggers 
        matched: {hits}") return round(score, 4)
    def _role_match(self, seg: SegmentFeatures, cont: ContactFeatures, reasons: list[str]) -> float: 
        if not seg.target_roles:
            return 0.5 if not cont.roles: return 0.0 for role in cont.roles: for target in 
            seg.target_roles:
                if target in role or role in target: reasons.append(f"role match: {role}") return 
                    1.0
        # По категории
        if "decision_maker" in cont.role_categories: return 0.7 if "champion" in 
        cont.role_categories or "influencer" in cont.role_categories:
            return 0.5 return 0.2 ```
### Интеграция
В `SearchOrchestrator._run_job` уже вызывается `self._scorer.score(...)`. Меняется только 
реализация.
### Тесты
```python def test_scorer_industry_exact(): scorer = Scorer() seg = {"scoring_weights": 
    {"industry_match": 1.0, "size_match": 0.0, "geo_match": 0.0, "pain_match": 0.0, "trigger_match": 
    0.0, "role_match": 0.0}, "firmographic": {"industries": ["Производство"]}} comp = {"industry": 
    {"value": "Производство", "confidence": 0.9, "evidence": []}} score, breakdown, _ = 
    scorer.score(normalized_company=comp, contacts=[], segment=seg) assert score == 1.0 assert 
    breakdown["industry_match"] == 1.0
def test_scorer_industry_partial(): scorer = Scorer() seg = {"scoring_weights": {"industry_match": 
    1.0, "size_match": 0.0, "geo_match": 0.0, "pain_match": 0.0, "trigger_match": 0.0, "role_match": 
    0.0}, "firmographic": {"industries": ["Производство"]}} comp = {"industry": {"value": 
    "Промышленное производство", "confidence": 0.9, "evidence": []}} score, _, _ = 
    scorer.score(normalized_company=comp, contacts=[], segment=seg) assert score == 0.7
def test_scorer_geo_mismatch(): scorer = Scorer() seg = {"scoring_weights": {"geo_match": 1.0, 
    "industry_match": 0.0, "size_match": 0.0, "pain_match": 0.0, "trigger_match": 0.0, "role_match": 
    0.0}, "firmographic": {"geos": ["RU"]}} comp = {"locations": [{"country": {"value": "US", 
    "confidence": 1.0, "evidence": []}, "is_hq": True}]} score, _, _ = 
    scorer.score(normalized_company=comp, contacts=[], segment=seg) assert score == 0.0
```
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/test_scorer.py -v 
--cov=sourcing_service.scoring --cov-report=term-missing
# Ожидание: coverage >= 95% E2E — score распределение После реального поиска:
bash scripts/psql.sh -c "SELECT score, count(*) FROM search_job_items WHERE tenant_id='$TENANT' AND 
job_id='$JOB_ID' GROUP BY score ORDER BY score DESC LIMIT 20;"
# Ожидание: распределение score (не все 1.0)
```
## Подсказки
- **`min_threshold` = 0.5** — отсекаем слабых. Настраивается через env. - **Breakdown** — 
сохраняется в `SearchJobItem.score_breakdown` для аналитики. - **Reasons** — пока не сохраняются, но 
можно добавить в breakdown как `{"reasons": [...]}`. - **Нейтральные значения 0.5** — если у 
сегмента нет данных для компонента, не наказываем кандидата.
## Анти-паттерны
- ❌ Не падать, если поля отсутствуют — использовать нейтральные значения. - ❌ Не забывать `round` 
— score должен быть чистым. - ❌ Не использовать LLM для скоринга — детерминированно. ---
# Задача 2C.3.2 — Retry, cancel, timeout, dead-letter
**Файл:** `docs/tasks/sprint-2c/2c.3.2-reliability.md`
## Цель
Добавить надёжность: timeout на job, реальная отмена (не только флаг), retry для failed items, 
dead-letter для повторных фейлов.
## Зависимости
2C.1.5.
## Детали
### Timeout на job
В `Settings`: ```python job_timeout_seconds: int = Field(1800, alias="SOURCING_JOB_TIMEOUT") # 30 
минут ``` В `_run_job` — обернуть в `asyncio.wait_for`: ```python try:
    await asyncio.wait_for(self._run_job_inner(job_id, ...), 
    timeout=self._settings.job_timeout_seconds)
except asyncio.TimeoutError:
    # помечаем job как failed с error="timeout"
```
### Реальная отмена
Сейчас cancel только ставит статус. Нужно реально прерывать задачу. Решение: - Хранить 
`asyncio.Task` в `self._running_tasks: dict[UUID, asyncio.Task]`. - `cancel` → `task.cancel()`. - В 
`_run_job` — проверять флаг отмены между этапами. ```python
# в orchestrator:
def __init__(...): self._running_tasks: dict[UUID, asyncio.Task] = {} async def create_and_run(...): 
    ... task = asyncio.create_task(self._run_job(job.id, ...)) self._running_tasks[job.id] = task 
    task.add_done_callback(lambda _: self._running_tasks.pop(job.id, None))
async def cancel(...): job = await self._repo.get(job_id) if job and job.status in ("pending", 
    "running"):
        task = self._running_tasks.get(job_id) if task: task.cancel() job.status = "cancelled" ... 
```
### Retry для failed items
Эндпоинт `POST /searches/{id}/retry-failed`: - Берёт все items со `status="failed"`. - Перезапускает 
нормализацию + persist для них. - Обновляет counts.
### Dead-letter
Если item фейлится 3 раза (счётчик в `metadata` item), помечаем `status="dead"`. Не переобрабатываем 
автоматически.
### Тесты
- Timeout: запустить job с mock-коннектором, который висит, проверить, что через timeout статус 
`failed`. - Cancel: запустить job, отменить, проверить, что task отменён. - Retry: создать failed 
item, вызвать retry, проверить, что повторно обработан.
## Acceptance criteria
```bash
# Timeout Запустить job с коннектором, который долго работает, проверить failed через timeout Cancel
curl -X POST $BASE/searches/$JOB_ID/cancel -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: c1" | jq 
.status
# Ожидание: cancelled Retry
curl -X POST $BASE/searches/$JOB_ID/retry-failed -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: r1" 
| jq .
# Ожидание: job перезапущен для failed items
```
## Подсказки
- **Timeout важен** — иначе job может висеть вечно на застрявшем HTTP-запросе. - **Cancel через 
task.cancel()** — реально прерывает. Флаг проверять только между этапами, не внутри. - **Retry — 
отдельный эндпоинт**, не автоматический.
## Анти-паттерны
- ❌ Не оставлять job в running без timeout. - ❌ Не делать retry бесконечным. - ❌ Не забывать 
cleanup `_running_tasks` при завершении. ---
# Задача 2C.3.3 — Аналитика поисков + cost tracking
**Файл:** `docs/tasks/sprint-2c/2c.3.3-analytics.md`
## Цель
Эндпоинт `GET /searches/stats` с агрегатами: сколько поисков, средний yield, стоимость, 
распределение по источникам.
## Зависимости
2C.1.5.
## Детали
### `GET /searches/stats`
```python class SearchStats(BaseModel): period_days: int total_jobs: int completed_jobs: int 
    failed_jobs: int total_candidates_raw: int total_candidates_persisted: int 
    total_companies_created: int total_contacts_created: int total_cost_usd: float avg_duration_ms: 
    int avg_yield_percent: float # persisted / raw by_source: dict[str, dict] # {source: 
    {candidates: N, persisted: M}} by_status: dict[str, int]
``` Запросы: ```sql -- Агрегаты по jobs за период SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE 
  status='completed') as completed, COUNT(*) FILTER (WHERE status='failed') as failed, 
  SUM(candidates_raw_count) as raw, SUM(candidates_persisted_count) as persisted, 
  SUM(companies_created) as companies, SUM(contacts_created) as contacts, SUM(total_cost_usd) as 
  cost, AVG(duration_ms) FILTER (WHERE duration_ms IS NOT NULL) as avg_duration
FROM search_jobs WHERE tenant_id = :tid AND created_at > NOW() - INTERVAL '30 days'; -- По 
источникам SELECT source, COUNT(*) as items, COUNT(*) FILTER (WHERE status='persisted') as persisted 
FROM search_job_items WHERE tenant_id = :tid AND created_at > NOW() - INTERVAL '30 days' GROUP BY 
source; ```
## Acceptance criteria
```bash curl -H "X-Tenant-ID: $TENANT" "$BASE/searches/stats?period_days=30" | jq .
# Ожидание: агрегаты
```
## Подсказки
- **`period_days`** — параметр, по умолчанию 30. - **Кэшировать stats на 60 секунд в Redis** — чтобы 
не долбить БД. Опционально.
## Анти-паттерны
- ❌ Не считать stats без индексов — медленно. - ❌ Не забывать фильтр по tenant_id (RLS сам 
отфильтрует, но лучше явно). ---
# Задача 2C.3.4 — Тесты, E2E, CI
**Файл:** `docs/tasks/sprint-2c/2c.3.4-tests.md`
## Цель
Довести покрытие до 80%+, E2E с реальным ICP, обновить CI.
## Детали
### E2E
Полный цикл: 1. Создать Brief → ICP (2B). 2. Взять `segment_id` из ICP. 3. `POST /searches` с 
`sources=["serper", "registry"]`. 4. Дождаться `completed`. 5. Проверить, что в contact-store 
появились компании. 6. Проверить score распределение. 7. Проверить cost.
### Обновить CI
Добавить `sourcing-service` в matrix build-images.
## Acceptance criteria
```bash uv run pytest services/sourcing-service/tests/ -v --cov=sourcing_service 
--cov-report=term-missing
# Ожидание: coverage >= 80% E2E на dev — см. выше CI зелёный
``` ---
## Финальная E2E-проверка Спринта 2C
```bash export TENANT="<sandbox>" export SOURCING="https://sourcing.dev.aitler.ru" export 
BRIEF="https://brief.dev.aitler.ru" export ICP="https://icp.dev.aitler.ru" export 
CS="https://contact-store.dev.aitler.ru"
# 1. Brief (если нет)
BRIEF_ID=$(curl -sX POST $BRIEF/briefs \ -H "Content-Type: application/json" \ -H "X-Tenant-ID: 
  $TENANT" \ -H "Idempotency-Key: e2e-b1" \ -d '{"text": "Производим гидроборты для грузовиков. Ищем 
  дистрибьюторов ПТО в РФ."}' | jq -r .id)
# 2. Ответить на вопросы
for i in $(seq 0 10); do STATUS=$(curl -s -H "X-Tenant-ID: $TENANT" $BRIEF/briefs/$BRIEF_ID | jq -r 
  .status) [ "$STATUS" = "complete" ] && break PENDING=$(curl -s -H "X-Tenant-ID: $TENANT" 
  $BRIEF/briefs/$BRIEF_ID | jq '[.qa_history | to_entries[] | select(.value.answered_at == null) | 
  .key][0]') [ "$PENDING" = "null" ] && break curl -sX POST $BRIEF/briefs/$BRIEF_ID/answers \
    -H "Content-Type: application/json" \ -H "X-Tenant-ID: $TENANT" \ -H "Idempotency-Key: e2e-a-$i" 
    \ -d "{\"question_index\": $PENDING, \"answer\": \"Ответ $i: дистрибьюторы ПТО, средний чек 
    500k, РФ.\"}" > /dev/null
done
# 3. ICP
ICP_RESP=$(curl -sX POST $ICP/icps \ -H "Content-Type: application/json" \ -H "X-Tenant-ID: $TENANT" 
  \ -H "Idempotency-Key: e2e-icp1" \ -d '{"brief_id": "'$BRIEF_ID'"}')
ICP_ID=$(echo $ICP_RESP | jq -r .id) SEGMENT_ID=$(echo $ICP_RESP | jq -r '.payload.segments[0].id') 
echo "ICP: $ICP_ID, segment: $SEGMENT_ID"
# 4. Search
JOB_RESP=$(curl -sX POST $SOURCING/searches \ -H "Content-Type: application/json" \ -H "X-Tenant-ID: 
  $TENANT" \ -H "Idempotency-Key: e2e-s1" \ -d '{"icp_id": "'$ICP_ID'", "segment_id": 
  "'$SEGMENT_ID'", "sources": ["serper"], "limit_per_source": 20}')
JOB_ID=$(echo $JOB_RESP | jq -r .id) echo "Job: $JOB_ID"
# 5. Ждать завершения
for i in $(seq 1 60); do sleep 5 STATUS=$(curl -s -H "X-Tenant-ID: $TENANT" 
  $SOURCING/searches/$JOB_ID | jq -r .status) echo "iter $i: $STATUS" [ "$STATUS" = "completed" ] && 
  break [ "$STATUS" = "failed" ] && break
done
# 6. Финальные метрики
curl -s -H "X-Tenant-ID: $TENANT" $SOURCING/searches/$JOB_ID | jq '{ status, candidates_raw_count, 
  candidates_normalized_count, candidates_persisted_count, companies_created, companies_merged, 
  contacts_created, contacts_merged, total_cost_usd, duration_ms
}'
# Ожидание: completed, persisted >= 3 7. Компании в contact-store
curl -s -H "X-Tenant-ID: $TENANT" "$CS/companies?limit=200" | jq 'length'
# Ожидание: >= companies_created 8. Stats
curl -s -H "X-Tenant-ID: $TENANT" "$SOURCING/searches/stats?period_days=30" | jq .
# Ожидание: агрегаты 9. События NATS
bash scripts/nats-cli.sh stream view CONTACTS --last 20 | grep -E 
"contacts\.(search_started|found|enriched)"
# Ожидание: search_started и found точно 10. LLM calls
bash scripts/psql.sh -c "SELECT task_type, count(*), sum(cost_usd) FROM llm_calls WHERE 
tenant_id='$TENANT' AND task_type LIKE 'sourcing%' GROUP BY task_type;"
# Ожидание: sourcing_normalize_candidate_v1, count >= persisted 11. Retry failed
curl -sX POST $SOURCING/searches/$JOB_ID/retry-failed \ -H "X-Tenant-ID: $TENANT" \ -H 
  "Idempotency-Key: e2e-retry" | jq .status
# Ожидание: 200 12. RLS
OTHER="00000000-0000-0000-0000-000000000000" curl -s -H "X-Tenant-ID: $OTHER" 
$SOURCING/searches/$JOB_ID -w "\n%{http_code}\n"
# Ожидание: 404 13. CI
git push origin develop
# Зелёные
``` **Если все 13 пунктов проходят — Спринт 2C закрыт.** ---
## Проверка: что я перепроверил
- [x] Порядок задач: 2C.1.1 → 2C.1.2 → 2C.1.3 → 2C.1.4 → 2C.1.5 → 2C.2.1 → 2C.2.2 → 2C.2.3 → 2C.3.1 
→ 2C.3.2 → 2C.3.3 → 2C.3.4, зависимости соблюдены. - [x] Connector — чистая абстракция, без 
бизнес-логики. - [x] `RawCandidate.dedup_key()` — дедуп между коннекторами. - [x] Rate limiter в 
каждом коннекторе. - [x] `Normalizer` не импортирует ICP — передаётся `segment_context` строкой. - 
[x] Evidence сохраняется везде. - [x] Scorer — детерминированный, break-down по компонентам. - [x] 
`asyncio.create_task` + `_running_tasks` — не GC'нется. - [x] Фоновая задача использует свою 
session. - [x] Idempotency-Key для contact-store (sourcing:job:item). - [x] Cost tracking для 
каждого коннектора. - [x] Timeout, cancel, retry-failed. - [x] Stats endpoint. - [x] RLS на 
search_jobs и search_job_items. - [x] Mypy strict, ruff, pytest. - [x] Никаких cross-service 
импортов. - [x] Никаких `print`, `time.sleep`, `datetime.utcnow`. ---
## Что дальше (Спринт 3)
После закрытия 2C переходим к **`composer-service` + `review-queue`** — генерация писем и очередь на 
ревью. Это уже outreach, не sourcing. **Что от тебя нужно сейчас:** 1. Разложить эти 12 задач по 
файлам в `docs/tasks/sprint-2c/`. 2. Дать агенту: «Начинай с 2C.1.1, иди по порядку, 2C.1 — 
обязательно до конца, потом 2C.2, потом 2C.3». 3. Сообщить мне, когда 2C закрыт (или если агент 
застрял — особенно на 2C.1.5, там самая сложная оркестрация). Если хочешь что-то поправить сейчас — 
скажи. Особенно интересует: - **Rusprofile vs DaData** — я выбрал DaData как основной. Если у тебя 
есть доступ к Rusprofile API — скажи, поменяю.
- **Playwright** — оставляем гибрид (httpx + fallback), или сразу Playwright для всех?
