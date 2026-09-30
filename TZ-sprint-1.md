# Спринт 1 — `brief-service` (intake + LLM-интервью)
Проверил: зависимости от Спринта 0 (контракты, db, nats-client, common, llm-gateway) соблюдены, 
порядок задач логичен, acceptance criteria проверяемы, нет противоречий с `docs/contracts.md` и 
`docs/infra.md`. Каждая задача самодостаточна.
## Что такое `brief-service` и почему он важный
Это первый «умный» сервис платформы. Он превращает **сырой ввод** (текст, ссылку, ответы, 
транскрипт) в **структурированный Brief v1**, из которого потом строится ICP и весь outreach. От 
качества этого шага зависит всё дальше: плохой бриф → плохой ICP → мусорный sourcing → письма в 
молоко. Ключевая идея: **адаптивный intake**. Минимум данных от пользователя, дальше LLM задаёт 
уточняющие вопросы по одному, пока не наберётся достаточная полнота (`completeness_score >= 0.85`).
## Архитектура сервиса (что внутри)
``` ┌─────────────────────────────────┐ │ brief-service │ │ │ HTTP POST /briefs ──►│ API layer 
  (routes) │
                      │ │ │ │ ▼ │ │ BriefService (бизнес-логика) │ │ │ │ │ ├──► BriefRepository │ │ 
                      ├──► QuestionGenerator ───┼──► llm-gateway │ ├──► BriefExtractor ──────┼──► 
                      llm-gateway │ ├──► CompletenessScorer │ │ └──► Publisher (NATS) │ │ │ │ 
                      Events: │ │ - brief.created │ │ - brief.questions_asked │ │ - brief.updated │ 
                      │ - brief.completed │ └─────────────────────────────────┘
``` **Что сервис делает:** 1. Принимает raw input (текст, URL, файлы, транскрипт). 2. Извлекает 
через LLM структурированные поля Brief (identity, offering, targeting_hints, outreach_goals). 3. 
Считает `completeness_score`. 4. Если не хватает данных — генерирует уточняющие вопросы, по одному 
на итерацию. 5. Принимает ответы, обновляет Brief. 6. Когда `completeness_score >= 0.85` — переводит 
в `complete` и публикует `brief.completed`. **Что НЕ делает (осознанно):** - Не строит ICP — это 
задача `icp-service` (Спринт 2). - Не ищет контакты — это `sourcing-service` (Спринт 2). - Не 
генерирует письма — это `composer-service` (Спринт 3). - Не имеет UI — только API. ---
# Задача 1.1 — Каркас `brief-service`
**Файл:** `docs/tasks/sprint-1/1.1-bootstrap.md`
## Цель
Создать каркас сервиса по образцу `tenant-service`: структура директорий, config, main.py, 
Dockerfile, миграции (пустые), эндпоинт `/healthz`. Сервис поднимается, healthcheck зелёный, больше 
ничего не делает.
## Зависимости
Спринт 0 закрыт.
## Что создать
``` services/brief-service/ ├── pyproject.toml ├── Dockerfile ├── alembic.ini ├── migrations/ │ ├── 
env.py │ ├── script.py.mako │ └── versions/ │ └── 0001_create_briefs.py # таблица + RLS, минимальная 
├── src/brief_service/ │ ├── __init__.py │ ├── main.py │ ├── config.py │ ├── models.py # Brief 
(SQLAlchemy) │ ├── schemas.py # API-схемы (отдельно от contracts) │ ├── repository.py │ ├── 
service.py │ ├── events.py │ ├── api/ │ │ ├── __init__.py │ │ ├── routes.py │ │ └── deps.py │ └── 
llm/ │ ├── __init__.py │ ├── client.py # обёртка над llm-client │ └── prompts/ │ ├── __init__.py │ 
├── extract_brief.py │ └── generate_questions.py └── tests/
    ├── __init__.py ├── conftest.py ├── test_api.py └── test_service.py ```
## Детали реализации
### `pyproject.toml`
```toml [project] name = "brief-service" version = "0.1.0" requires-python = ">=3.12" dependencies = 
[
    "fastapi>=0.115", "uvicorn[standard]>=0.32", "pydantic>=2.9", "pydantic-settings>=2.6", 
    "sqlalchemy[asyncio]>=2.0.36", "asyncpg>=0.30", "alembic>=1.14", "redis>=5.2", "httpx>=0.27", 
    "structlog>=24.4", "tenacity>=9.0", "common", "contracts", "db", "nats-client", "llm-client",
] [build-system] requires = ["hatchling"] build-backend = "hatchling.build" 
[tool.hatch.build.targets.wheel] packages = ["src/brief_service"] ```
### `config.py`
```python from pydantic import Field from common.config import BaseServiceSettings class 
Settings(BaseServiceSettings):
    service_name: str = Field("brief-service", alias="SERVICE_NAME") llm_gateway_url: str = 
    Field(..., alias="LLM_GATEWAY_URL")
    # Лимиты intake
    max_raw_text_length: int = Field(50_000, alias="BRIEF_MAX_RAW_TEXT_LENGTH") 
    max_urls_per_request: int = Field(10, alias="BRIEF_MAX_URLS") max_questions_per_iteration: int = 
    Field(1, alias="BRIEF_MAX_QUESTIONS_PER_ITER") completeness_threshold: float = Field(0.85, 
    alias="BRIEF_COMPLETENESS_THRESHOLD")
    # LLM
    llm_model: str = Field("deepseek-chat", alias="BRIEF_LLM_MODEL") llm_temperature: float = 
    Field(0.3, alias="BRIEF_LLM_TEMPERATURE") llm_max_tokens: int = Field(4096, 
    alias="BRIEF_LLM_MAX_TOKENS")
``` **Важно:** `completeness_threshold` — конфигурируемый. В dev можно поставить 0.7, чтобы быстрее 
тестировать.
### `models.py`
```python from sqlalchemy import Float, String, Text from sqlalchemy.dialects.postgresql import 
JSONB from sqlalchemy.orm import Mapped, mapped_column from db.base import Base from db.mixins 
import (
    MetadataMixin, SchemaVersionMixin, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin, ) class 
Brief(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "briefs" status: Mapped[str] = mapped_column(String(32), nullable=False, 
    default="draft", index=True) completeness_score: Mapped[float] = mapped_column(Float, 
    nullable=False, default=0.0) raw_input: Mapped[dict] = mapped_column(JSONB, nullable=False, 
    default=dict) qa_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list) 
    identity: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict) offering: 
    Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict) targeting_hints: Mapped[dict] 
    = mapped_column(JSONB, nullable=False, default=dict) outreach_goals: Mapped[dict] = 
    mapped_column(JSONB, nullable=False, default=dict) missing_info: Mapped[list] = 
    mapped_column(JSONB, nullable=False, default=list) created_by: Mapped[str] = 
    mapped_column(String(128), nullable=False, default="system") trace_id: Mapped[str | None] = 
    mapped_column(String(64), nullable=True)
``` **Важно:** в БД храним как JSONB, но при чтении валидируем через Pydantic-модель 
`contracts.Brief`. Модель SQLAlchemy — «сырая», контракт — «умная».
### `schemas.py`
API-схемы **отличаются** от контрактов. Контракт `contracts.Brief` — это то, что хранится и 
передаётся между сервисами. API-схемы — то, что принимает и отдаёт HTTP. ```python from datetime 
import datetime from uuid import UUID from pydantic import BaseModel, ConfigDict, Field, HttpUrl 
class RawInputSubmit(BaseModel):
    """Первичный ввод по проекту.""" model_config = ConfigDict(extra="forbid") text: str | None = 
    Field(None, max_length=50_000) urls: list[HttpUrl] = Field(default_factory=list, max_length=10) 
    transcript: str | None = Field(None, max_length=100_000)
class AnswerSubmit(BaseModel): """Ответ на уточняющий вопрос.""" model_config = 
    ConfigDict(extra="forbid") question_index: int = Field(ge=0) answer: str = Field(min_length=1, 
    max_length=10_000)
class BriefRead(BaseModel): """Полный Brief для чтения.""" model_config = ConfigDict(extra="ignore") 
    id: UUID tenant_id: UUID status: str completeness_score: float raw_input: dict qa_history: 
    list[dict] identity: dict offering: dict targeting_hints: dict outreach_goals: dict 
    missing_info: list[dict] schema_version: str created_at: datetime updated_at: datetime 
    created_by: str
class BriefSummary(BaseModel): """Краткая версия для списков.""" model_config = 
    ConfigDict(extra="ignore") id: UUID status: str completeness_score: float project_name: str | 
    None created_at: datetime updated_at: datetime
class QuestionItem(BaseModel): question: str priority: str # high | medium | low asked_at: datetime 
    answered_at: datetime | None generated_by: str question_template_id: str | None = None
class MissingInfoItem(BaseModel): field: str why_needed: str priority: str ```
### `migrations/versions/0001_create_briefs.py`
```python from alembic import op import sqlalchemy as sa from sqlalchemy.dialects import postgresql 
revision = "0001_create_briefs" down_revision = None branch_labels = None depends_on = None def 
upgrade() -> None:
    op.create_table( "briefs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), 
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True), 
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"), 
        sa.Column("completeness_score", sa.Float, nullable=False, server_default="0"), 
        sa.Column("raw_input", postgresql.JSONB, nullable=False, server_default="{}"), 
        sa.Column("qa_history", postgresql.JSONB, nullable=False, server_default="[]"), 
        sa.Column("identity", postgresql.JSONB, nullable=False, server_default="{}"), 
        sa.Column("offering", postgresql.JSONB, nullable=False, server_default="{}"), 
        sa.Column("targeting_hints", postgresql.JSONB, nullable=False, server_default="{}"), 
        sa.Column("outreach_goals", postgresql.JSONB, nullable=False, server_default="{}"), 
        sa.Column("missing_info", postgresql.JSONB, nullable=False, server_default="[]"), 
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"), 
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"), 
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"), 
        sa.Column("trace_id", sa.String(64), nullable=True), sa.Column("created_at", 
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), 
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, 
        server_default=sa.func.now()),
    ) op.create_index("ix_briefs_tenant_status", "briefs", ["tenant_id", "status"]) 
    op.create_index("ix_briefs_tenant_created", "briefs", ["tenant_id", "created_at"])
    # GIN по JSONB для будущих запросов "найди брифы с industry=..."
    op.execute("CREATE INDEX ix_briefs_identity_gin ON briefs USING gin (identity jsonb_path_ops)") 
    op.execute("CREATE INDEX ix_briefs_offering_gin ON briefs USING gin (offering jsonb_path_ops)") 
    op.execute("ALTER TABLE briefs ENABLE ROW LEVEL SECURITY") op.execute(
        """ CREATE POLICY briefs_tenant_isolation ON briefs USING (tenant_id = 
        current_setting('app.tenant_id', true)::uuid) WITH CHECK (tenant_id = 
        current_setting('app.tenant_id', true)::uuid) """
    ) def downgrade() -> None: op.execute("DROP POLICY IF EXISTS briefs_tenant_isolation ON briefs") 
    op.drop_index("ix_briefs_offering_gin") op.drop_index("ix_briefs_identity_gin") 
    op.drop_index("ix_briefs_tenant_created") op.drop_index("ix_briefs_tenant_status") 
    op.drop_table("briefs")
``` **Важно:** GIN-индексы по `identity` и `offering` — на будущее, когда будем искать «все брифы с 
industry=Промышленность». Это дешёво при создании.
### `main.py`
По образцу `tenant-service.main`. Отличия: - `Settings` из `brief_service.config`. - Роутер `briefs` 
подключается (создадим в 1.4). - В lifespan создаём `LLMClient` (из `llm_client`) и `Publisher`.
### `api/routes.py` (пустой пока)
```python from fastapi import APIRouter router = APIRouter(prefix="/briefs", tags=["briefs"])
# Эндпоинты появятся в задачах 1.4+
```
### `Dockerfile`
Скопировать из `tenant-service/Dockerfile`, поменять `--package tenant-service` → `--package 
brief-service` и `CMD ["uvicorn", "brief_service.main:app", ...]`.
### Добавить в `infra/docker-compose.dev.yml`
```yaml brief-service: <<: *service-defaults build: context: .. dockerfile: 
      services/brief-service/Dockerfile
    container_name: outreach-brief-service environment: <<: *common-env SERVICE_NAME: brief-service 
      SERVICE_PORT: "8000" DATABASE_URL: 
      postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach} 
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222 REDIS_URL: 
      redis://:${REDIS_PASSWORD}@redis:6379/2 LLM_GATEWAY_URL: http://llm-gateway:8000 
      BRIEF_COMPLETENESS_THRESHOLD: "0.85" LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on: postgres: condition: service_healthy nats: condition: service_healthy redis: 
        condition: service_healthy
      llm-gateway: condition: service_started labels: caddy: brief.dev.aitler.ru 
      caddy.reverse_proxy: "{{upstreams 8000}}"
    healthcheck: test: ["CMD", "python", "-c", "import urllib.request; 
      urllib.request.urlopen('http://localhost:8000/healthz')"] interval: 10s timeout: 5s retries: 5 
      start_period: 15s
```
### Обновить `scripts/migrate.sh`
Добавить `brief-service` в `SERVICES_WITH_DB`.
## Acceptance criteria
```bash
# 1. Миграция применяется
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev run --rm brief-service alembic 
upgrade head
# Ожидание: Applying 0001_create_briefs... OK 2. Сервис поднимается
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d brief-service docker 
compose -f infra/docker-compose.dev.yml --env-file .env.dev logs --tail=20 brief-service
# Ожидание: service_started 3. Healthcheck
curl -fsS https://brief.dev.aitler.ru/healthz
# Ожидание: {"status":"ok"} 4. RLS работает
docker compose ... exec postgres psql -U outreach -d outreach -c "\d+ briefs"
# Ожидание: таблица есть, RLS enabled 5. OpenAPI доступен
curl -fsS https://brief.dev.aitler.ru/openapi.json | jq .info.title
# Ожидание: "Brief Service"
```
## Подсказки
- **Не наследуй `contracts.Brief` от `EntityBase` в SQLAlchemy-модели.** Держи их отдельно: 
SQLAlchemy — «сырая» модель, Pydantic-контракт — «умная». Конвертация через 
`BriefContract.model_validate(brief_sa.model_dump() | {...})`. - **GIN-индексы по JSONB** создаются 
быстро, но занимают место. На dev можно пропустить, на prod — нужны. - **Обнови `SKIP_PATHS` в 
TenantMiddleware?** Нет — все эндпоинты `brief-service` тенант-скоупные, `X-Tenant-ID` обязателен.
## Анти-паттерны
- ❌ Не использовать `contracts.Brief` напрямую как SQLAlchemy-модель. - ❌ Не хранить 
`completeness_score` только в JSONB — вынести в колонку для индексов. - ❌ Не забыть добавить сервис 
в `migrate.sh`. - ❌ Не делать intake эндпоинт без `X-Tenant-ID`. ---
# Задача 1.2 — LLM-клиент и промпты
**Файл:** `docs/tasks/sprint-1/1.2-llm-client.md`
## Цель
Создать обёртку `LLMClient` для вызовов `llm-gateway` и модуль промптов с двумя основными задачами: 
1. **Extract Brief** — извлечь структурированные поля из raw input. 2. **Generate Questions** — 
сгенерировать уточняющие вопросы на основе неполного Brief.
## Зависимости
1.1.
## Что создать
``` services/brief-service/src/brief_service/llm/ ├── __init__.py ├── client.py ├── json_utils.py 
└── prompts/
    ├── __init__.py ├── base.py ├── extract_brief.py └── generate_questions.py ```
### `client.py`
Обёртка над `llm_client.LLMClient` (из `libs/llm-client`). Если в Спринте 0 `libs/llm-client` не 
реализован — реализовать здесь. ```python import json import structlog from typing import Any, 
TypeVar import httpx from pydantic import BaseModel, ValidationError from tenacity import retry, 
stop_after_attempt, wait_exponential, retry_if_exception_type from brief_service.config import 
Settings logger = structlog.get_logger() T = TypeVar("T", bound=BaseModel) class 
LLMGatewayError(Exception):
    """Ошибка при вызове llm-gateway.""" class LLMClient: """Обёртка над llm-gateway для 
    brief-service.""" def __init__(self, settings: Settings) -> None:
        self._settings = settings self._client = httpx.AsyncClient( 
            base_url=settings.llm_gateway_url, timeout=httpx.Timeout(120.0, connect=10.0),
        ) @retry( stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), 
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)), reraise=True,
    ) async def complete( self, *, tenant_id: str, task_type: str, system: str | None, user: str, 
        trace_id: str = "", temperature: float | None = None, max_tokens: int | None = None, 
        json_mode: bool = False, use_cache: bool = False,
    ) -> str: payload = { "task_type": task_type, "system": system, "user": user, "model": 
            self._settings.llm_model, "temperature": temperature if temperature is not None else 
            self._settings.llm_temperature, "max_tokens": max_tokens or 
            self._settings.llm_max_tokens, "json_mode": json_mode, "use_cache": use_cache,
        }
        response = await self._client.post( "/v1/complete", json=payload, headers={ "X-Tenant-ID": 
                tenant_id, "X-Trace-Id": trace_id, "Idempotency-Key": 
                f"{task_type}:{trace_id}:{hash(user)}",
            },
        ) response.raise_for_status() data = response.json() return data["text"] async def 
    complete_json(
        self, *, tenant_id: str, task_type: str, system: str, user: str, output_schema: type[T], 
        trace_id: str = "", temperature: float | None = None, max_tokens: int | None = None,
    ) -> T: """Вызывает LLM в JSON-режиме и валидирует результат по Pydantic-схеме.""" raw = await 
        self.complete(
            tenant_id=tenant_id, task_type=task_type, system=system, user=user, trace_id=trace_id, 
            temperature=temperature, max_tokens=max_tokens, json_mode=True, use_cache=False,
        ) parsed = json_utils.parse_json_strict(raw) try: return 
            output_schema.model_validate(parsed)
        except ValidationError as e: logger.warning( "llm_schema_validation_failed", task=task_type, 
                error=str(e), raw_preview=raw[:500],
            ) raise LLMGatewayError(f"LLM output failed schema validation: {e}") from e async def 
    close(self) -> None:
        await self._client.aclose() ```
### `json_utils.py`
LLM иногда оборачивает JSON в markdown-блок. Нужен надёжный парсер. ```python import json import re 
from brief_service.llm.client import LLMGatewayError _FENCE_RE = 
re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL) def parse_json_strict(raw: str) -> dict:
    """Парсит JSON из ответа LLM, снимая markdown-обёртку если есть.""" text = raw.strip()
    # Снимаем ```json ... ```
    m = _FENCE_RE.match(text) if m: text = m.group(1).strip()
    # Ищем первую { и последнюю } — иногда LLM добавляет пояснения
    first = text.find("{") last = text.rfind("}") if first != -1 and last != -1 and last > first: 
        text = text[first : last + 1]
    try: return json.loads(text) except json.JSONDecodeError as e: raise LLMGatewayError(f"LLM 
        returned invalid JSON: {e}") from e
```
### `prompts/base.py`
```python from dataclasses import dataclass @dataclass(frozen=True) class Prompt: system: str user: 
    str task_type: str
SYSTEM_COMMON = """Ты — ассистент, который помогает структурировать информацию о B2B-проектах для 
последующего outreach. Правила: - Отвечай ТОЛЬКО валидным JSON, без markdown-обёрток и пояснений. - 
Если данные отсутствуют — используй null, не выдумывай. - Все строки — на русском языке (если 
исходные данные на русском), иначе — на языке исходных данных. - Не добавляй поля, которых нет в 
схеме. - Будь кратким и конкретным. """ ```
### `prompts/extract_brief.py`
```python from brief_service.llm.prompts.base import SYSTEM_COMMON, Prompt EXTRACT_SCHEMA = """ { 
  "identity": {
    "project_name": "string | null", "company_name": "string | null", "company_url": "string | 
    null", "one_liner": "string | null", "industry": "string | null", "sub_industry": "string | 
    null", "language": "BCP-47 (например 'ru', 'en')", "geo_primary": ["ISO 3166-1 alpha-2"], 
    "geo_secondary": ["ISO 3166-1 alpha-2"]
  },
  "offering": { "what_we_sell": "string", "categories": ["string"], "differentiators": ["string"], 
    "proof_points": ["string"], "price_range": {
      "min": number | null, "max": number | null, "currency": "ISO 4217 | null", "model": "fixed | 
      subscription | usage | custom | unknown"
    },
    "sales_cycle_days_estimate": integer | null
  },
  "targeting_hints": { "known_competitors": ["string"], "known_customers_examples": ["string"], 
    "must_have_criteria": ["string"], "must_not_have_criteria": ["string"], "geography_notes": 
    "string | null", "company_size_hint": "smb | mid | enterprise | any | null", "role_hints": 
    ["string"]
  },
  "outreach_goals": { "primary_goal": "lead_gen | partnership | hiring | pr | research | other", 
    "goal_description": "string | null", "target_meetings_per_month": integer | null, 
    "tone_of_voice": "formal | casual | technical | friendly | neutral", "forbidden_topics": 
    ["string"], "required_mentions": ["string"]
  }
}
""" def build_extract_prompt( *, raw_text: str | None, urls: list[str], transcript: str | None, 
    website_contents: list[dict] | None = None,
) -> Prompt: """Собирает промпт для извлечения Brief из сырого ввода.""" parts = ["Извлеки 
    структурированную информацию о проекте из следующих данных.\n"] if raw_text:
        parts.append(f"<текст>\n{raw_text}\n</текст>\n") if urls: parts.append("<ссылки>") for u in 
        urls:
            parts.append(f" <url>{u}</url>") parts.append("</ссылки>\n") if website_contents: 
        parts.append("<содержимое_сайтов>") for item in website_contents:
            parts.append(f" <site url=\"{item['url']}\">") parts.append(item["text"][:8000]) # 
            ограничиваем parts.append(" </site>")
        parts.append("</содержимое_сайтов>\n") if transcript: 
        parts.append(f"<транскрипт>\n{transcript}\n</транскрипт>\n")
    parts.append( "Верни JSON ровно такой структуры (без markdown, без пояснений):\n" 
        f"{EXTRACT_SCHEMA}\n\n" "Если каких-то данных нет — используй null или пустой массив. Не 
        выдумывай."
    ) return Prompt( system=SYSTEM_COMMON, user="\n".join(parts), task_type="brief_extract", ) ```
### `prompts/generate_questions.py`
```python from brief_service.llm.prompts.base import SYSTEM_COMMON, Prompt QUESTIONS_SCHEMA = """ { 
  "questions": [
    { "question": "string (на русском, конкретный, открытый, не да/нет)", "why_needed": "string 
      (зачем этот вопрос)", "target_field": "string (поле Brief, которое закрывает вопрос, например 
      'offering.price_range.min')", "priority": "high | medium | low"
    }
  ]
}
""" def build_generate_questions_prompt( *, brief_json: str, missing_fields: list[dict], 
    already_asked: list[str], max_questions: int = 1,
) -> Prompt: asked_block = "\n".join(f"- {q}" for q in already_asked) or "(нет)" missing_block = 
    "\n".join(
        f"- {m['field']}: {m['why_needed']} (приоритет: {m['priority']})" for m in missing_fields ) 
    user = f"""Есть частично заполненный Brief проекта:
<brief> {brief_json} </brief> Не хватает следующих данных (в порядке приоритета): {missing_block} 
Уже были заданы эти вопросы (не повторяй их): {asked_block} Сгенерируй РОВНО {max_questions} 
уточняющий вопрос, который: 1. Закрывает самое приоритетное недостающее поле. 2. Сформулирован на 
русском, конкретно, открыто (не да/нет). 3. Учитывает контекст уже имеющихся данных (не спрашивай 
то, что можно вывести). 4. Не повторяет ранее заданные вопросы. Верни JSON ровно такой структуры 
(без markdown, без пояснений): {QUESTIONS_SCHEMA} """
    return Prompt( system=SYSTEM_COMMON, user=user, task_type="brief_generate_questions", ) ```
### Тесты
`tests/test_json_utils.py`: ```python import pytest from brief_service.llm.json_utils import 
parse_json_strict from brief_service.llm.client import LLMGatewayError def test_parse_plain_json():
    assert parse_json_strict('{"a": 1}') == {"a": 1} def test_parse_markdown_fenced(): assert 
    parse_json_strict('```json\n{"a": 1}\n```') == {"a": 1}
def test_parse_with_explanation(): raw = 'Вот результат:\n{"a": 1}\nНадеюсь, поможет.' assert 
    parse_json_strict(raw) == {"a": 1}
def test_parse_invalid_raises(): with pytest.raises(LLMGatewayError): parse_json_strict("not json at 
        all")
```
## Acceptance criteria
```bash
# 1. Импорт
uv run python -c "from brief_service.llm.client import LLMClient; from 
brief_service.llm.prompts.extract_brief import build_extract_prompt; from 
brief_service.llm.prompts.generate_questions import build_generate_questions_prompt; print('OK')"
# 2. Тесты
uv run pytest services/brief-service/tests/test_json_utils.py -v
# 3. Реальный вызов llm-gateway (интеграционный) В тесте с testcontainers или через docker compose 
# exec
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev exec -T brief-service python - 
<<'PY' import asyncio from brief_service.config import Settings from brief_service.llm.client import 
LLMClient async def main():
    s = Settings() c = LLMClient(s) text = await c.complete( 
        tenant_id="00000000-0000-0000-0000-000000000001", task_type="test", system="Отвечай 
        кратко.", user="Скажи 'ok'.", max_tokens=10,
    ) print(repr(text)) await c.close() asyncio.run(main()) PY
# Ожидание: 'ok' или похожее
```
## Подсказки
- **`complete_json`** — ключевой метод. Всегда валидирует результат через Pydantic. - 
**`use_cache=False`** по умолчанию для генеративных задач. Для extract можно `True`, если вход не 
меняется. - **Idempotency-Key** в вызове llm-gateway: `f"{task_type}:{trace_id}:{hash(user)}"`. Если 
тот же вызов повторится — вернётся кэш. - **Промпты — код.** Храни их в отдельных файлах, не 
разбрасывай по сервису. - **Версионирование промптов:** имя функции `build_extract_prompt` + 
константа в файле `PROMPT_VERSION = "v1"`. Добавляй в `task_type`: `brief_extract_v1`. Это критично 
для A/B.
## Анти-паттерны
- ❌ Не строить JSON-промпт конкатенацией строк без экранирования входных данных. - ❌ Не доверять 
LLM слепо — всегда `model_validate`. - ❌ Не использовать `json.loads` без предварительной очистки 
markdown. - ❌ Не кэшировать генеративные вызовы. ---
# Задача 1.3 — CompletenessScorer и MissingInfoAnalyzer
**Файл:** `docs/tasks/sprint-1/1.3-completeness.md`
## Цель
Реализовать два алгоритма: 1. **CompletenessScorer** — считает `completeness_score` по формуле из 
`docs/contracts.md`. 2. **MissingInfoAnalyzer** — определяет, какие поля не заполнены и насколько 
они важны. Оба — **детерминированные** (не LLM), чтобы не жечь токены и не зависеть от 
нестабильности модели. LLM используется **только** для генерации вопросов (задача 1.2), а «что не 
хватает» определяется кодом.
## Зависимости
1.1.
## Что создать
``` services/brief-service/src/brief_service/scoring/ ├── __init__.py ├── completeness.py ├── 
missing_info.py └── constants.py services/brief-service/tests/ ├── test_completeness.py └── 
test_missing_info.py ```
### `constants.py`
```python """Веса и пороги для скоринга Brief. Менять только при осознанном решении."""
# Веса групп верхнего уровня (сумма = 1.0)
GROUP_WEIGHTS = { "identity": 0.25, "offering": 0.30, "targeting_hints": 0.20, "outreach_goals": 
    0.25,
}
# Веса полей внутри групп (сумма внутри группы = 1.0)
FIELD_WEIGHTS = { "identity": { "project_name": 0.15, "company_name": 0.10, "company_url": 0.10, 
        "one_liner": 0.15, "industry": 0.20, "sub_industry": 0.05, "language": 0.05, "geo_primary": 
        0.20,
    },
    "offering": { "what_we_sell": 0.30, "categories": 0.15, "differentiators": 0.20, "proof_points": 
        0.10, "price_range": 0.15, "sales_cycle_days_estimate": 0.10,
    },
    "targeting_hints": { "known_customers_examples": 0.20, "must_have_criteria": 0.30, 
        "must_not_have_criteria": 0.15, "company_size_hint": 0.15, "role_hints": 0.20,
    },
    "outreach_goals": { "primary_goal": 0.40, "goal_description": 0.20, "tone_of_voice": 0.20, 
        "forbidden_topics": 0.10, "required_mentions": 0.10,
    },
}
# Приоритет полей для missing_info
FIELD_PRIORITY = { "identity.project_name": "high", "identity.industry": "high", 
    "identity.geo_primary": "high", "identity.company_url": "medium", "identity.one_liner": 
    "medium", "identity.company_name": "medium", "identity.language": "low", 
    "identity.sub_industry": "low", "offering.what_we_sell": "high", "offering.differentiators": 
    "high", "offering.categories": "medium", "offering.proof_points": "medium", 
    "offering.price_range": "medium", "offering.sales_cycle_days_estimate": "low", 
    "targeting_hints.must_have_criteria": "high", "targeting_hints.known_customers_examples": 
    "medium", "targeting_hints.role_hints": "medium", "targeting_hints.company_size_hint": "medium", 
    "targeting_hints.must_not_have_criteria": "low", "outreach_goals.primary_goal": "high", 
    "outreach_goals.tone_of_voice": "medium", "outreach_goals.goal_description": "medium", 
    "outreach_goals.forbidden_topics": "low", "outreach_goals.required_mentions": "low",
}
# Человекочитаемые объяснения, зачем нужно поле
FIELD_WHY_NEEDED = { "identity.project_name": "Без названия проекта сложно идентифицировать бриф", 
    "identity.industry": "Отрасль определяет ЦА и источники поиска", "identity.geo_primary": 
    "География критична для таргетинга", "identity.company_url": "Сайт компании — ключевой источник 
    для OSINT", "identity.one_liner": "Краткое описание помогает в персонализации писем", 
    "identity.company_name": "Нужно для поиска компании в реестрах", "offering.what_we_sell": "Без 
    этого невозможно построить оффер", "offering.differentiators": "Определяет, чем цеплять в 
    письме", "offering.categories": "Помогает сегментировать ЦА", "offering.proof_points": "Кейсы и 
    цифры повышают доверие", "offering.price_range": "Влияет на сегментацию по размеру клиента", 
    "targeting_hints.must_have_criteria": "Определяет, кого искать", 
    "targeting_hints.known_customers_examples": "Помогает найти похожих клиентов", 
    "targeting_hints.role_hints": "Определяет, к кому обращаться", "outreach_goals.primary_goal": 
    "Цель outreach определяет тон и CTA", "outreach_goals.tone_of_voice": "Влияет на стиль письма",
}
```
### `completeness.py`
```python from typing import Any from brief_service.scoring.constants import FIELD_WEIGHTS, 
GROUP_WEIGHTS def _is_filled(value: Any) -> bool:
    """Определяет, считается ли поле заполненным.""" if value is None: return False if 
    isinstance(value, str):
        return len(value.strip()) > 0 if isinstance(value, (list, dict)): return len(value) > 0 if 
    isinstance(value, (int, float)):
        # 0 — валидное значение, но для цен это скорее "не заполнено"
        return True return True def _field_score(group_name: str, field_name: str, data: dict) -> 
float:
    """Скор одного поля: 1.0 если заполнено, 0.0 если нет. Особые случаи: - price_range: считается 
    заполненным, если model != "unknown" ИЛИ есть min/max. - geo_primary: пустой массив — не 
    заполнено. """ if group_name == "offering" and field_name == "price_range":
        pr = data.get("price_range") or {} if not isinstance(pr, dict): return 0.0 model = 
        pr.get("model") has_numbers = pr.get("min") is not None or pr.get("max") is not None if 
        model and model != "unknown":
            return 1.0 if has_numbers: return 1.0 return 0.0 value = data.get(field_name) return 1.0 
    if _is_filled(value) else 0.0
def compute_completeness(brief_data: dict) -> float: """Считает общий completeness_score (0.0–1.0). 
    brief_data — dict с ключами identity, offering, targeting_hints, outreach_goals. """ total = 0.0 
    for group_name, group_weight in GROUP_WEIGHTS.items():
        group_data = brief_data.get(group_name) or {} if not isinstance(group_data, dict): 
            group_data = {}
        group_score = 0.0 field_weights = FIELD_WEIGHTS.get(group_name, {}) for field_name, 
        field_weight in field_weights.items():
            group_score += field_weight * _field_score(group_name, field_name, group_data) total += 
        group_weight * group_score
    return round(min(max(total, 0.0), 1.0), 4) ```
### `missing_info.py`
```python from datetime import datetime, timezone from brief_service.scoring.constants import ( 
    FIELD_PRIORITY, FIELD_WHY_NEEDED, FIELD_WEIGHTS,
) from brief_service.scoring.completeness import _field_score _PRIORITY_ORDER = {"high": 0, 
"medium": 1, "low": 2} def analyze_missing_info(brief_data: dict) -> list[dict]:
    """Возвращает список недостающих полей, отсортированных по приоритету. Каждый элемент: { 
      "field": "identity.industry", "why_needed": "...", "priority": "high" | "medium" | "low",
    }
    """ missing: list[dict] = [] for group_name, field_weights in FIELD_WEIGHTS.items(): group_data 
        = brief_data.get(group_name) or {} if not isinstance(group_data, dict):
            group_data = {} for field_name in field_weights: if _field_score(group_name, field_name, 
            group_data) < 1.0:
                full_path = f"{group_name}.{field_name}" missing.append({ "field": full_path, 
                    "why_needed": FIELD_WHY_NEEDED.get(full_path, ""), "priority": 
                    FIELD_PRIORITY.get(full_path, "medium"),
                })
    missing.sort(key=lambda m: _PRIORITY_ORDER.get(m["priority"], 1)) return missing def 
get_next_priority_field(brief_data: dict) -> dict | None:
    """Возвращает самое приоритетное незаполненное поле или None, если всё заполнено.""" missing = 
    analyze_missing_info(brief_data) return missing[0] if missing else None
```
### Тесты
`tests/test_completeness.py`: ```python import pytest from brief_service.scoring.completeness import 
compute_completeness def test_empty_brief_scores_zero():
    assert compute_completeness({}) == 0.0 def test_full_brief_scores_one(): data = { "identity": { 
            "project_name": "X", "company_name": "X LLC", "company_url": "https://x.com", 
            "one_liner": "X делает Y", "industry": "IT", "sub_industry": "SaaS", "language": "ru", 
            "geo_primary": ["RU"],
        },
        "offering": { "what_we_sell": "SaaS", "categories": ["crm"], "differentiators": ["fast"], 
            "proof_points": ["1000 клиентов"], "price_range": {"model": "subscription", "currency": 
            "RUB"}, "sales_cycle_days_estimate": 30,
        },
        "targeting_hints": { "known_customers_examples": ["A", "B"], "must_have_criteria": ["РФ"], 
            "must_not_have_criteria": ["госсектор"], "company_size_hint": "smb", "role_hints": 
            ["CTO"],
        },
        "outreach_goals": { "primary_goal": "lead_gen", "goal_description": "Ищем 20 лидов в месяц", 
            "tone_of_voice": "technical", "forbidden_topics": ["политика"], "required_mentions": 
            ["гарантия"],
        },
    }
    assert compute_completeness(data) == 1.0 def test_partial_brief(): data = { "identity": 
        {"project_name": "X", "industry": "IT"}, "offering": {"what_we_sell": "SaaS"}, 
        "targeting_hints": {}, "outreach_goals": {"primary_goal": "lead_gen"},
    }
    score = compute_completeness(data) assert 0.0 < score < 1.0
    # Точное значение зависит от весов, но должно быть ~0.35
    assert 0.25 < score < 0.45 ``` `tests/test_missing_info.py`: ```python from 
brief_service.scoring.missing_info import analyze_missing_info, get_next_priority_field def 
test_missing_info_sorted_by_priority():
    missing = analyze_missing_info({}) priorities = [m["priority"] for m in missing]
    # high идут первыми
    assert priorities[0] == "high"
    # порядок неубывающий
    order = {"high": 0, "medium": 1, "low": 2} assert [order[p] for p in priorities] == 
    sorted([order[p] for p in priorities])
def test_next_priority_field(): nxt = get_next_priority_field({}) assert nxt is not None assert 
    nxt["priority"] == "high" assert nxt["field"] in {"identity.project_name", "identity.industry", 
    "identity.geo_primary", "offering.what_we_sell", "targeting_hints.must_have_criteria", 
    "outreach_goals.primary_goal"}
def test_no_missing_when_all_filled(): data = { "identity": {"project_name": "X", "company_name": 
        "X", "company_url": "u", "one_liner": "o", "industry": "IT", "sub_industry": "SaaS", 
        "language": "ru", "geo_primary": ["RU"]}, "offering": {"what_we_sell": "x", "categories": 
        ["a"], "differentiators": ["b"], "proof_points": ["c"], "price_range": {"model": "custom"}, 
        "sales_cycle_days_estimate": 1}, "targeting_hints": {"known_customers_examples": ["a"], 
        "must_have_criteria": ["b"], "must_not_have_criteria": ["c"], "company_size_hint": "smb", 
        "role_hints": ["d"]}, "outreach_goals": {"primary_goal": "lead_gen", "goal_description": 
        "x", "tone_of_voice": "neutral", "forbidden_topics": ["a"], "required_mentions": ["b"]},
    }
    assert get_next_priority_field(data) is None ```
## Acceptance criteria
```bash uv run pytest services/brief-service/tests/test_completeness.py 
services/brief-service/tests/test_missing_info.py -v
# Ожидание: все passed
uv run mypy services/brief-service
# Ожидание: Success
```
## Подсказки
- **Не используй LLM для скоринга.** Это детерминированная задача, LLM тут только навредит 
(галлюцинации, стоимость). - **Веса — в константах.** Если нужно пересчитать — меняешь в одном 
месте. - **`_field_score` — приватная**, но импортируется в `missing_info`. Это осознанно: общая 
логика «заполнено/нет» должна быть в одном месте. - **Округление до 4 знаков** — чтобы не было 
0.8500000001 в JSON.
## Анти-паттерны
- ❌ Не хардкодить веса в функции — только в `constants.py`. - ❌ Не считать `completeness_score` 
через LLM. - ❌ Не забывать `round()`, иначе float-хвосты в БД. - ❌ Не смешивать `_is_filled` и 
`_field_score` — второй использует первый, но добавляет особые случаи. ---
# Задача 1.4 — `BriefService` + intake endpoint
**Файл:** `docs/tasks/sprint-1/1.4-intake.md`
## Цель
Реализовать основной сценарий: пользователь отправляет raw input → сервис создаёт Brief, извлекает 
поля через LLM, считает completeness, генерирует первый уточняющий вопрос. Публикует `brief.created` 
и `brief.questions_asked`.
## Зависимости
1.1, 1.2, 1.3.
## Что создать / изменить
- `services/brief-service/src/brief_service/repository.py` - 
`services/brief-service/src/brief_service/service.py` - 
`services/brief-service/src/brief_service/events.py` - 
`services/brief-service/src/brief_service/api/routes.py` - 
`services/brief-service/src/brief_service/api/deps.py` - 
`services/brief-service/src/brief_service/fetcher.py` (загрузка сайтов по URL) - Тесты
### `fetcher.py`
Простенький загрузчик содержимого сайтов по URL. Без JS-рендеринга на этом этапе. ```python import 
structlog import httpx from bs4 import BeautifulSoup from tenacity import retry, stop_after_attempt, 
wait_exponential, retry_if_exception_type logger = structlog.get_logger() @retry(
    stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), 
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)), reraise=False,
) async def _fetch_one(client: httpx.AsyncClient, url: str) -> dict | None: try: resp = await 
        client.get(url, follow_redirects=True) resp.raise_for_status()
    except Exception as e: logger.warning("fetch_failed", url=url, error=str(e)) return None soup = 
    BeautifulSoup(resp.text, "html.parser")
    # Убираем скрипты/стили
    for tag in soup(["script", "style", "noscript"]): tag.decompose() text = 
    soup.get_text(separator="\n", strip=True)
    # Ограничиваем
    text = text[:20_000] title = soup.title.string.strip() if soup.title and soup.title.string else 
    "" description = "" meta = soup.find("meta", attrs={"name": "description"}) if meta and 
    meta.get("content"):
        description = meta["content"].strip() return { "url": str(resp.url), "title": title, 
        "description": description, "text": text,
    }
async def fetch_websites(urls: list[str], *, timeout: float = 15.0) -> list[dict]: """Загружает 
    содержимое сайтов. Пропускает недоступные.""" if not urls:
        return [] results: list[dict] = [] async with httpx.AsyncClient( 
        timeout=httpx.Timeout(timeout, connect=5.0), headers={"User-Agent": "OutreachOS/0.1 
        (+https://aitler.ru)"},
    ) as client: for url in urls: item = await _fetch_one(client, url) if item is not None: 
                results.append(item)
    return results ``` **Добавить `beautifulsoup4` и `lxml` в зависимости `brief-service`.**
### `repository.py`
```python from uuid import UUID from sqlalchemy import select from sqlalchemy.ext.asyncio import 
AsyncSession from brief_service.models import Brief class BriefRepository:
    def __init__(self, session: AsyncSession) -> None: self._s = session async def get(self, 
    brief_id: UUID) -> Brief | None:
        return await self._s.get(Brief, brief_id) async def list( self, *, tenant_id: UUID, status: 
        str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[Brief]: stmt = select(Brief).where(Brief.tenant_id == tenant_id) if status is not 
        None:
            stmt = stmt.where(Brief.status == status) stmt = 
        stmt.order_by(Brief.created_at.desc()).limit(limit).offset(offset) return list((await 
        self._s.execute(stmt)).scalars().all())
    async def add(self, brief: Brief) -> Brief: self._s.add(brief) await self._s.flush() return 
        brief
```
### `events.py`
```python from uuid import UUID from nats_client.publisher import Publisher from 
nats_client.subjects import Subjects from brief_service.models import Brief async def 
emit_brief_created(publisher: Publisher, brief: Brief, *, trace_id: str) -> None:
    await publisher.publish( Subjects.BRIEF_CREATED, tenant_id=brief.tenant_id, payload={ "brief": { 
                "id": str(brief.id), "status": brief.status, "completeness_score": 
                brief.completeness_score,
            }
        },
        trace_id=trace_id, correlation_id=brief.id, ) async def emit_brief_questions_asked( 
    publisher: Publisher, brief: Brief, *, questions: list[dict], trace_id: str,
) -> None: await publisher.publish( Subjects.BRIEF_QUESTIONS_ASKED, tenant_id=brief.tenant_id, 
        payload={
            "brief_id": str(brief.id), "questions": [ {"question": q["question"], "priority": 
                q["priority"]} for q in questions
            ],
        },
        trace_id=trace_id, correlation_id=brief.id, ) async def emit_brief_completed(publisher: 
Publisher, brief: Brief, *, trace_id: str) -> None:
    await publisher.publish( Subjects.BRIEF_COMPLETED, tenant_id=brief.tenant_id, payload={ "brief": 
            {
                "id": str(brief.id), "completeness_score": brief.completeness_score,
            }
        },
        trace_id=trace_id, correlation_id=brief.id, ) async def emit_brief_updated(publisher: 
Publisher, brief: Brief, *, trace_id: str) -> None:
    await publisher.publish( Subjects.BRIEF_UPDATED, tenant_id=brief.tenant_id, payload={ "brief": { 
                "id": str(brief.id), "status": brief.status, "completeness_score": 
                brief.completeness_score,
            }
        },
        trace_id=trace_id, correlation_id=brief.id, ) ```
### `service.py`
Ключевой сервис. Логика: 1. `create_from_raw_input(...)`: создаёт Brief, извлекает поля, считает 
completeness, генерирует первый вопрос, публикует события. 2. `answer_question(...)`: добавляет 
ответ в qa_history, переизвлекает поля (частично — только затронутые), пересчитывает completeness, 
генерирует следующий вопрос ИЛИ завершает. 3. `get`, `list`. ```python from datetime import 
datetime, timezone from uuid import UUID import structlog from common.errors import NotFoundError, 
ValidationError from brief_service.config import Settings from brief_service.llm.client import 
LLMClient from brief_service.llm.prompts.extract_brief import build_extract_prompt from 
brief_service.llm.prompts.generate_questions import build_generate_questions_prompt from 
brief_service.models import Brief from brief_service.repository import BriefRepository from 
brief_service.scoring.completeness import compute_completeness from 
brief_service.scoring.missing_info import analyze_missing_info, get_next_priority_field from 
brief_service.fetcher import fetch_websites from nats_client.publisher import Publisher from 
brief_service import events logger = structlog.get_logger() class BriefService:
    def __init__( self, repo: BriefRepository, llm: LLMClient, publisher: Publisher, settings: 
        Settings,
    ) -> None: self._repo = repo self._llm = llm self._publisher = publisher self._settings = 
        settings
    async def create_from_raw_input( self, *, tenant_id: UUID, text: str | None, urls: list[str], 
        transcript: str | None, created_by: str, trace_id: str,
    ) -> Brief:
        # Валидация
        if not (text or urls or transcript): raise ValidationError("At least one of 
            text/urls/transcript is required")
        # Загружаем сайты
        website_contents = await fetch_websites(urls)
        # Извлекаем через LLM
        prompt = build_extract_prompt( raw_text=text, urls=urls, transcript=transcript, 
            website_contents=website_contents,
        ) extracted = await self._llm.complete_json( tenant_id=str(tenant_id), 
            task_type="brief_extract_v1", system=prompt.system, user=prompt.user, 
            output_schema=_ExtractSchema, # см. ниже trace_id=trace_id,
        )
        # Собираем Brief
        data = { "identity": extracted.identity.model_dump(), "offering": 
            extracted.offering.model_dump(), "targeting_hints": 
            extracted.targeting_hints.model_dump(), "outreach_goals": 
            extracted.outreach_goals.model_dump(),
        }
        completeness = compute_completeness(data) missing = analyze_missing_info(data) brief = 
        Brief(
            tenant_id=tenant_id, status="in_progress" if completeness < 
            self._settings.completeness_threshold else "complete", completeness_score=completeness, 
            raw_input={
                "text": text, "urls": urls, "transcript": transcript, "website_contents": [{"url": 
                w["url"], "title": w["title"]} for w in website_contents], "submitted_at": 
                datetime.now(timezone.utc).isoformat(),
            },
            qa_history=[], identity=data["identity"], offering=data["offering"], 
            targeting_hints=data["targeting_hints"], outreach_goals=data["outreach_goals"], 
            missing_info=missing, created_by=created_by, trace_id=trace_id,
        ) await self._repo.add(brief) await events.emit_brief_created(self._publisher, brief, 
        trace_id=trace_id)
        # Генерируем первый вопрос, если нужно
        if brief.status != "complete": await self._generate_and_append_question(brief, 
            trace_id=trace_id)
        if brief.status == "complete": await events.emit_brief_completed(self._publisher, brief, 
            trace_id=trace_id)
        return brief async def answer_question( self, *, brief_id: UUID, question_index: int, 
        answer: str, trace_id: str,
    ) -> Brief: brief = await self._repo.get(brief_id) if brief is None: raise NotFoundError(f"Brief 
            {brief_id} not found")
        qa = list(brief.qa_history or []) if question_index < 0 or question_index >= len(qa): raise 
            ValidationError(f"Question index {question_index} out of range")
        item = dict(qa[question_index]) if item.get("answered_at") is not None: raise 
            ValidationError(f"Question {question_index} already answered")
        item["answer"] = answer item["answered_at"] = datetime.now(timezone.utc).isoformat() 
        qa[question_index] = item brief.qa_history = qa
        # Переизвлекаем поля — на основе исходного ввода + Q&A
        await self._re_extract(brief, trace_id=trace_id)
        # Пересчитываем
        data = { "identity": brief.identity, "offering": brief.offering, "targeting_hints": 
            brief.targeting_hints, "outreach_goals": brief.outreach_goals,
        }
        brief.completeness_score = compute_completeness(data) brief.missing_info = 
        analyze_missing_info(data) if brief.completeness_score >= 
        self._settings.completeness_threshold:
            brief.status = "complete" await self._repo._s.flush() await 
            events.emit_brief_updated(self._publisher, brief, trace_id=trace_id) await 
            events.emit_brief_completed(self._publisher, brief, trace_id=trace_id)
        else: brief.status = "in_progress" await self._repo._s.flush() await 
            events.emit_brief_updated(self._publisher, brief, trace_id=trace_id) await 
            self._generate_and_append_question(brief, trace_id=trace_id)
        return brief async def _re_extract(self, brief: Brief, *, trace_id: str) -> None: 
        """Переизвлекает поля Brief с учётом накопленных Q&A.""" qa = brief.qa_history or [] qa_text 
        = "\n".join(
            f"В: {q['question']}\nО: {q.get('answer', '(не отвечено)')}" for q in qa ) raw = 
        brief.raw_input or {} prompt = build_extract_prompt(
            raw_text=raw.get("text"), urls=raw.get("urls", []), transcript=raw.get("transcript"), 
            website_contents=raw.get("website_contents"),
        )
        # Дополняем Q&A
        prompt_with_qa = type(prompt)( system=prompt.system, user=prompt.user + 
            f"\n\n<уточнения>\n{qa_text}\n</уточнения>\n", task_type=prompt.task_type,
        ) extracted = await self._llm.complete_json( tenant_id=str(brief.tenant_id), 
            task_type="brief_extract_v1", system=prompt_with_qa.system, user=prompt_with_qa.user, 
            output_schema=_ExtractSchema, trace_id=trace_id,
        ) brief.identity = extracted.identity.model_dump() brief.offering = 
        extracted.offering.model_dump() brief.targeting_hints = 
        extracted.targeting_hints.model_dump() brief.outreach_goals = 
        extracted.outreach_goals.model_dump()
    async def _generate_and_append_question(self, brief: Brief, *, trace_id: str) -> None: 
        next_field = get_next_priority_field({
            "identity": brief.identity, "offering": brief.offering, "targeting_hints": 
            brief.targeting_hints, "outreach_goals": brief.outreach_goals,
        })
        if next_field is None: return already_asked = [q["question"] for q in (brief.qa_history or 
        [])] missing = brief.missing_info or [] import json as _json prompt = 
        build_generate_questions_prompt(
            brief_json=_json.dumps({ "identity": brief.identity, "offering": brief.offering, 
                "targeting_hints": brief.targeting_hints, "outreach_goals": brief.outreach_goals,
            }, ensure_ascii=False, indent=2),
            missing_fields=missing, already_asked=already_asked, 
            max_questions=self._settings.max_questions_per_iteration,
        ) result = await self._llm.complete_json( tenant_id=str(brief.tenant_id), 
            task_type="brief_generate_questions_v1", system=prompt.system, user=prompt.user, 
            output_schema=_QuestionsSchema, trace_id=trace_id,
        ) now = datetime.now(timezone.utc).isoformat() qa = list(brief.qa_history or []) for q in 
        result.questions:
            qa.append({ "question": q.question, "priority": q.priority, "asked_at": now, 
                "answered_at": None, "generated_by": f"llm:{self._settings.llm_model}", 
                "question_template_id": None,
            })
        brief.qa_history = qa await self._repo._s.flush() await events.emit_brief_questions_asked( 
            self._publisher, brief, questions=[q.model_dump() for q in result.questions], 
            trace_id=trace_id,
        ) async def get(self, brief_id: UUID) -> Brief: brief = await self._repo.get(brief_id) if 
        brief is None:
            raise NotFoundError(f"Brief {brief_id} not found") return brief async def list(self, *, 
    tenant_id: UUID, status: str | None, limit: int, offset: int) -> list[Brief]:
        return await self._repo.list(tenant_id=tenant_id, status=status, limit=limit, offset=offset) 
```
### Схемы для LLM output (`_ExtractSchema`, `_QuestionsSchema`)
Отдельные Pydantic-модели **только для валидации ответа LLM**. Не путать с `contracts.Brief` и 
API-схемами. Создать `services/brief-service/src/brief_service/llm/schemas.py`: ```python from 
pydantic import BaseModel, ConfigDict, Field class _PriceRange(BaseModel):
    model_config = ConfigDict(extra="ignore") min: float | None = None max: float | None = None 
    currency: str | None = None model: str = "unknown"
class _Identity(BaseModel): model_config = ConfigDict(extra="ignore") project_name: str | None = 
    None company_name: str | None = None company_url: str | None = None one_liner: str | None = None 
    industry: str | None = None sub_industry: str | None = None language: str = "ru" geo_primary: 
    list[str] = Field(default_factory=list) geo_secondary: list[str] = Field(default_factory=list)
class _Offering(BaseModel): model_config = ConfigDict(extra="ignore") what_we_sell: str = "" 
    categories: list[str] = Field(default_factory=list) differentiators: list[str] = 
    Field(default_factory=list) proof_points: list[str] = Field(default_factory=list) price_range: 
    _PriceRange = Field(default_factory=_PriceRange) sales_cycle_days_estimate: int | None = None
class _TargetingHints(BaseModel): model_config = ConfigDict(extra="ignore") known_competitors: 
    list[str] = Field(default_factory=list) known_customers_examples: list[str] = 
    Field(default_factory=list) must_have_criteria: list[str] = Field(default_factory=list) 
    must_not_have_criteria: list[str] = Field(default_factory=list) geography_notes: str | None = 
    None company_size_hint: str | None = None role_hints: list[str] = Field(default_factory=list)
class _OutreachGoals(BaseModel): model_config = ConfigDict(extra="ignore") primary_goal: str = 
    "lead_gen" goal_description: str | None = None target_meetings_per_month: int | None = None 
    tone_of_voice: str = "neutral" forbidden_topics: list[str] = Field(default_factory=list) 
    required_mentions: list[str] = Field(default_factory=list)
class _ExtractSchema(BaseModel): model_config = ConfigDict(extra="ignore") identity: _Identity = 
    Field(default_factory=_Identity) offering: _Offering = Field(default_factory=_Offering) 
    targeting_hints: _TargetingHints = Field(default_factory=_TargetingHints) outreach_goals: 
    _OutreachGoals = Field(default_factory=_OutreachGoals)
class _Question(BaseModel): model_config = ConfigDict(extra="ignore") question: str why_needed: str 
    = "" target_field: str = "" priority: str = "medium"
class _QuestionsSchema(BaseModel): model_config = ConfigDict(extra="ignore") questions: 
    list[_Question] = Field(default_factory=list)
``` Импортировать в `service.py`: ```python from brief_service.llm.schemas import _ExtractSchema, 
_QuestionsSchema ```
### `api/routes.py`
```python from uuid import UUID from fastapi import APIRouter, Depends, Query, Request, status from 
common.context import get_tenant_id, get_trace_id from common.errors import ValidationError from 
brief_service.api.deps import get_publisher, get_service from brief_service.schemas import (
    AnswerSubmit, BriefRead, BriefSummary, RawInputSubmit, ) from brief_service.service import 
BriefService router = APIRouter(prefix="/briefs", tags=["briefs"]) @router.post("", 
response_model=BriefRead, status_code=status.HTTP_201_CREATED) async def create_brief(
    data: RawInputSubmit, request: Request, svc: BriefService = Depends(get_service), 
    publisher=Depends(get_publisher),
) -> BriefRead: tenant_id = get_tenant_id() if tenant_id is None: raise ValidationError("X-Tenant-ID 
        required")
    brief = await svc.create_from_raw_input( tenant_id=tenant_id, text=data.text, urls=[str(u) for u 
        in data.urls], transcript=data.transcript, created_by=request.headers.get("X-User-Id", 
        "anonymous"), trace_id=get_trace_id() or "",
    ) return BriefRead.model_validate(brief, from_attributes=True) @router.get("/{brief_id}", 
response_model=BriefRead) async def get_brief(
    brief_id: UUID, svc: BriefService = Depends(get_service), ) -> BriefRead: brief = await 
    svc.get(brief_id) return BriefRead.model_validate(brief, from_attributes=True)
@router.get("", response_model=list[BriefSummary]) async def list_briefs( status_filter: str | None 
    = Query(None, alias="status"), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, 
    ge=0), svc: BriefService = Depends(get_service),
) -> list[BriefSummary]: tenant_id = get_tenant_id() if tenant_id is None: raise 
        ValidationError("X-Tenant-ID required")
    briefs = await svc.list(tenant_id=tenant_id, status=status_filter, limit=limit, offset=offset) 
    return [
        BriefSummary( id=b.id, status=b.status, completeness_score=b.completeness_score, 
            project_name=(b.identity or {}).get("project_name"), created_at=b.created_at, 
            updated_at=b.updated_at,
        ) for b in briefs ] @router.post("/{brief_id}/answers", response_model=BriefRead) async def 
answer_question(
    brief_id: UUID, data: AnswerSubmit, svc: BriefService = Depends(get_service), ) -> BriefRead: 
    brief = await svc.answer_question(
        brief_id=brief_id, question_index=data.question_index, answer=data.answer, 
        trace_id=get_trace_id() or "",
    ) return BriefRead.model_validate(brief, from_attributes=True) ``` **Важно:** 
`BriefRead.model_validate(brief, from_attributes=True)` — Pydantic читает атрибуты 
SQLAlchemy-модели. Поля `identity` и т.д. уже dict (JSONB), так что `dict` в `BriefRead` совпадает.
### `api/deps.py`
```python from collections.abc import AsyncIterator from fastapi import Request from common.context 
import get_tenant_id from db.rls import set_tenant_context from db.session import 
async_session_factory from brief_service.repository import BriefRepository from 
brief_service.service import BriefService async def get_service(request: Request) -> 
AsyncIterator[BriefService]:
    tenant_id = get_tenant_id() async with async_session_factory() as session: async with 
        session.begin():
            if tenant_id is not None: await set_tenant_context(session, tenant_id) repo = 
            BriefRepository(session) yield BriefService(
                repo=repo, llm=request.app.state.llm, publisher=request.app.state.publisher, 
                settings=request.app.state.settings,
            ) async def get_publisher(request: Request): return request.app.state.publisher ```
### `main.py` (обновить)
Добавить в lifespan: ```python from brief_service.llm.client import LLMClient
# ...
app.state.llm = LLMClient(settings)
# ...
await app.state.llm.close() ```
## Acceptance criteria
```bash
# 1. Создать бриф
BRIEF=$(curl -sX POST https://brief.dev.aitler.ru/briefs \ -H "Content-Type: application/json" \ -H 
  "X-Tenant-ID: $TENANT" \ -H "Idempotency-Key: brief-create-$(date +%s)" \ -d '{
    "text": "Знакомый делает гидроборты для грузовиков, хочет выйти на дистрибьюторов в РФ", "urls": 
    ["https://example.com"]
  }')
echo $BRIEF | jq .
# Ожидание: { "id": "...", "status": "in_progress", "completeness_score": 0.xx, "identity": 
#   {"industry": "...", "geo_primary": ["RU"], ...}, "offering": {"what_we_sell": "...", ...}, 
#   "qa_history": [{"question": "...", "answered_at": null, ...}]
# }
BRIEF_ID=$(echo $BRIEF | jq -r .id)
# 2. Ответить на вопрос
curl -sX POST https://brief.dev.aitler.ru/briefs/$BRIEF_ID/answers \ -H "Content-Type: 
  application/json" \ -H "X-Tenant-ID: $TENANT" \ -H "Idempotency-Key: brief-answer-1" \ -d 
  '{"question_index": 0, "answer": "Работаем по всей России, средний чек 300 000 руб"}' | jq .
# Ожидание: обновлённый brief, completeness вырос 3. Проверить события
bash scripts/nats-cli.sh stream view BRIEFS | head -50
# Ожидание: brief.created, brief.questions_asked 4. Проверить LLM calls
bash scripts/psql.sh -c "SELECT task_type, count(*) FROM llm_calls WHERE tenant_id='$TENANT' GROUP 
BY task_type;"
# Ожидание: brief_extract_v1, brief_generate_questions_v1
```
## Подсказки
- **`website_contents`** сохраняем в raw_input только URL и title (не весь текст) — иначе БД 
распухнет. Полный текст — только в промпте. - **`_re_extract`** — важный момент: при каждом ответе 
мы **переизвлекаем** Brief заново, но уже с учётом Q&A. Это позволяет LLM «уточнить» уже извлечённые 
поля. - **`task_type`** с версией (`brief_extract_v1`) — для будущего A/B промптов. - 
**`correlation_id=brief.id`** — все события по брифу связаны одним correlation_id. Удобно для 
отладки.
## Анти-паттерны
- ❌ Не сохранять полный текст сайтов в БД — только выжимку. - ❌ Не запускать `_re_extract` без 
ответа — сначала валидация. - ❌ Не забывать `correlation_id` в событиях. - ❌ Не делать 
`answer_question` без проверки `answered_at is None`. - ❌ Не публиковать `brief.completed` дважды. 
---
# Задача 1.5 — Управление статусами и финализация
**Файл:** `docs/tasks/sprint-1/1.5-status.md`
## Цель
Добавить эндпоинты для ручного управления статусом Brief: `POST /briefs/{id}/complete` 
(форсированное завершение), `POST /briefs/{id}/abandon` (отказ), `POST /briefs/{id}/reset_question` 
(сбросить ответ, переспросить). Плюс `DELETE /briefs/{id}` (soft-delete через archived).
## Зависимости
1.4.
## Что создать
Дополнительные роуты в `api/routes.py` и методы в `service.py`: ```python 
@router.post("/{brief_id}/complete", response_model=BriefRead) async def force_complete(...):
    """Форсированное завершение — даже если completeness ниже порога.""" ... 
@router.post("/{brief_id}/abandon", response_model=BriefRead) async def abandon(...):
    """Помечает brief как abandoned.""" ... @router.post("/{brief_id}/reset-question", 
response_model=BriefRead) async def reset_question(...):
    """Сбрасывает ответ на конкретный вопрос и переспрашивает.""" ... @router.delete("/{brief_id}", 
status_code=204) async def archive(...):
    """Soft-delete.""" ... ``` Методы в `service.py`: ```python async def force_complete(self, 
brief_id: UUID, *, trace_id: str) -> Brief:
    brief = await self.get(brief_id) if brief.status == "complete": return brief brief.status = 
    "complete" await self._repo._s.flush() await events.emit_brief_completed(self._publisher, brief, 
    trace_id=trace_id) return brief
async def abandon(self, brief_id: UUID, *, reason: str | None, trace_id: str) -> Brief: brief = 
    await self.get(brief_id) brief.status = "abandoned" md = dict(brief.metadata_ or {}) 
    md["abandon_reason"] = reason md["abandoned_at"] = datetime.now(timezone.utc).isoformat() 
    brief.metadata_ = md await self._repo._s.flush() await 
    events.emit_brief_updated(self._publisher, brief, trace_id=trace_id) return brief
async def reset_question(self, brief_id: UUID, *, question_index: int, trace_id: str) -> Brief: 
    brief = await self.get(brief_id) qa = list(brief.qa_history or []) if question_index < 0 or 
    question_index >= len(qa):
        raise ValidationError(f"Question index {question_index} out of range") item = 
    dict(qa[question_index]) item["answer"] = None item["answered_at"] = None qa[question_index] = 
    item brief.qa_history = qa brief.status = "in_progress" await self._repo._s.flush() await 
    events.emit_brief_updated(self._publisher, brief, trace_id=trace_id) return brief
async def archive(self, brief_id: UUID, *, trace_id: str) -> None: brief = await self.get(brief_id) 
    brief.status = "archived" await self._repo._s.flush() await 
    events.emit_brief_updated(self._publisher, brief, trace_id=trace_id)
``` **Важно:** `archived` не входит в enum `BriefStatus` из `docs/contracts.md`. Проверить — там 
`draft | in_progress | complete | abandoned`. Значит `archived` либо добавить в контракт (breaking? 
нет, добавление — minor), либо использовать `abandoned` + флаг в metadata. **Решение:** добавить 
`archived` в `BriefStatus` в `libs/contracts/src/contracts/enums.py`. Это minor-изменение, версия 
остаётся `1.0`.
## Acceptance criteria
```bash
# 1. Force complete
curl -X POST https://brief.dev.aitler.ru/briefs/$BRIEF_ID/complete \ -H "X-Tenant-ID: $TENANT" \ -H 
  "Idempotency-Key: force-complete-1" | jq .status
# Ожидание: "complete" 2. Abandon
curl -X POST https://brief.dev.aitler.ru/briefs/$BRIEF_ID/abandon \ -H "X-Tenant-ID: $TENANT" \ -H 
  "Idempotency-Key: abandon-1" \ -d '{"reason": "Клиент передумал"}' | jq .status
# Ожидание: "abandoned" 3. Reset question
curl -X POST https://brief.dev.aitler.ru/briefs/$BRIEF_ID/reset-question \ -H "X-Tenant-ID: $TENANT" 
  \ -H "Idempotency-Key: reset-1" \ -d '{"question_index": 0}' | jq '.qa_history[0].answered_at'
# Ожидание: null 4. Archive
curl -X DELETE https://brief.dev.aitler.ru/briefs/$BRIEF_ID \ -H "X-Tenant-ID: $TENANT" \ -H 
  "Idempotency-Key: archive-1" -w "%{http_code}"
# Ожидание: 204
```
## Подсказки
- **Обновить `BriefStatus`** в `contracts/enums.py` — добавить `ARCHIVED = "archived"`. Это 
minor-изменение, обратно совместимо. - **`reason` для abandon** — в `metadata_`, не в отдельной 
колонке. Если понадобится индексировать — вынесем. - **Reset question** ставит статус обратно в 
`in_progress` — на случай, если brief был `complete` и мы хотим уточнить.
## Анти-паттерны
- ❌ Не удалять Brief физически — только `archived`. - ❌ Не забывать `emit_brief_updated` при смене 
статуса. - ❌ Не позволять reset на несуществующий индекс. ---
# Задача 1.6 — Тесты, E2E и CI
**Файл:** `docs/tasks/sprint-1/1.6-tests.md`
## Цель
Довести покрытие тестами до 85%+, добавить E2E-тест полного цикла intake → complete, обновить CI, 
добавить сервис в `deploy-dev.yml`.
## Зависимости
1.1–1.5.
## Что создать
### `tests/conftest.py`
```python import asyncio import os from collections.abc import AsyncIterator from uuid import uuid4 
import pytest import pytest_asyncio from httpx import ASGITransport, AsyncClient from 
brief_service.main import create_app TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"] 
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL) os.environ.setdefault("NATS_URL", 
"nats://test:test@localhost:4222") os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15") 
os.environ.setdefault("LLM_GATEWAY_URL", "http://localhost:8001") 
os.environ.setdefault("SERVICE_NAME", "brief-service-test") @pytest_asyncio.fixture async def app():
    app = create_app() async with app.router.lifespan_context(app): yield app 
@pytest_asyncio.fixture async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient( transport=ASGITransport(app=app), base_url="http://test", ) as ac: yield 
        ac
@pytest.fixture def tenant_id() -> str: return str(uuid4()) @pytest.fixture def headers(tenant_id: 
str) -> dict[str, str]:
    return {"X-Tenant-ID": tenant_id, "Idempotency-Key": str(uuid4())} ``` **Нужно:** 
`pytest-asyncio`, `httpx` в dev-зависимостях.
### `tests/test_api.py`
```python import pytest from httpx import AsyncClient @pytest.mark.asyncio async def 
test_create_brief_minimal(client: AsyncClient, headers):
    resp = await client.post( "/briefs", json={"text": "Компания делает CRM для малого бизнеса"}, 
        headers=headers,
    ) assert resp.status_code == 201 data = resp.json() assert data["status"] in ("in_progress", 
    "complete") assert data["completeness_score"] > 0 assert data["id"]
@pytest.mark.asyncio async def test_create_brief_requires_tenant(client: AsyncClient): resp = await 
    client.post(
        "/briefs", json={"text": "X"}, headers={"Idempotency-Key": "x"}, ) assert resp.status_code 
    == 400
@pytest.mark.asyncio async def test_create_brief_requires_input(client: AsyncClient, headers): resp 
    = await client.post("/briefs", json={}, headers=headers) assert resp.status_code == 422 # 
    pydantic validation
@pytest.mark.asyncio async def test_get_brief(client: AsyncClient, headers): create = await 
    client.post("/briefs", json={"text": "X делает Y"}, headers=headers) brief_id = 
    create.json()["id"] resp = await client.get(f"/briefs/{brief_id}", headers=headers) assert 
    resp.status_code == 200 assert resp.json()["id"] == brief_id
@pytest.mark.asyncio async def test_rls_isolation(client: AsyncClient):
    # Тенант A создаёт бриф
    headers_a = {"X-Tenant-ID": "00000000-0000-0000-0000-00000000000a", "Idempotency-Key": "a"} 
    create = await client.post("/briefs", json={"text": "A"}, headers=headers_a) brief_id = 
    create.json()["id"]
    # Тенант B не видит
    headers_b = {"X-Tenant-ID": "00000000-0000-0000-0000-00000000000b"} resp = await 
    client.get(f"/briefs/{brief_id}", headers=headers_b) assert resp.status_code == 404
```
### `tests/test_e2e.py`
Полный цикл: создать → ответить на все вопросы → получить complete. ```python import pytest from 
httpx import AsyncClient @pytest.mark.asyncio @pytest.mark.slow async def 
test_full_intake_cycle(client: AsyncClient, headers):
    # 1. Создать
    create = await client.post( "/briefs", json={ "text": ( "Мы — студия разработки на заказ. Делаем 
                веб и мобильные приложения " "для среднего бизнеса в России. Хотим найти клиентов в 
                ритейле и логистике."
            ),
        },
        headers=headers, ) assert create.status_code == 201 brief = create.json() brief_id = 
    brief["id"]
    # 2. Отвечать на вопросы, пока не complete
    max_iterations = 10 for _ in range(max_iterations): resp = await 
        client.get(f"/briefs/{brief_id}", headers=headers) brief = resp.json() if brief["status"] == 
        "complete":
            break
        # Ищем неотвеченный вопрос
        pending = [ (i, q) for i, q in enumerate(brief["qa_history"]) if q.get("answered_at") is 
            None
        ] assert pending, "No pending questions but brief not complete" idx, _ = pending[0] answer = 
        f"Ответ на вопрос {idx}: тестовые данные для покрытия" headers_ans = {**headers, 
        "Idempotency-Key": f"answer-{idx}-{brief_id}"} resp = await client.post(
            f"/briefs/{brief_id}/answers", json={"question_index": idx, "answer": answer}, 
            headers=headers_ans,
        ) assert resp.status_code == 200 assert brief["status"] == "complete", f"Brief not complete 
    after {max_iterations} iterations" assert brief["completeness_score"] >= 0.85
```
### Обновить `.github/workflows/ci.yml`
Добавить `brief-service` в matrix для build-images: ```yaml strategy: matrix: service: 
    [tenant-service, llm-gateway, brief-service]
```
### Обновить `scripts/migrate.sh` и `scripts/seed-sandbox.sh`
В `migrate.sh` — `brief-service` уже добавлен в 1.1. Проверить.
### Тестовый Docker Compose (опционально)
`infra/docker-compose.test.yml` — поднимает Postgres + NATS + Redis + fake-llm-gateway для CI. Если 
CI использует GitHub Services — можно обойтись без compose. **Fake llm-gateway:** простой FastAPI на 
8001, возвращает детерминированные ответы. Создать `tests/fake_llm_gateway.py`: ```python 
"""Запускается в тестах вместо реального llm-gateway.""" from fastapi import FastAPI from pydantic 
import BaseModel app = FastAPI() class CompleteRequest(BaseModel):
    task_type: str system: str | None = None user: str model: str = "deepseek-chat" temperature: 
    float = 0.7 max_tokens: int = 4096 json_mode: bool = False use_cache: bool = False
@app.post("/v1/complete") async def complete(req: CompleteRequest): if "brief_extract" in 
    req.task_type:
        text = 
        '{"identity":{"project_name":"Test","language":"ru","geo_primary":["RU"],"industry":"IT"},"offering":{"what_we_sell":"Test"},"targeting_hints":{},"outreach_goals":{"primary_goal":"lead_gen"}}'
    elif "generate_questions" in req.task_type: text = '{"questions":[{"question":"Уточните отрасль 
        клиентов?","why_needed":"для 
        таргетинга","target_field":"identity.industry","priority":"high"}]}'
    else: text = "ok" return {"text": text, "model": req.model, "tokens_in": 10, "tokens_out": 5, 
    "cost_usd": 0.0, "latency_ms": 100}
```
## Acceptance criteria
```bash
# 1. Все тесты проходят
uv run pytest services/brief-service/tests/ -v --cov=brief_service --cov-report=term-missing
# Ожидание: coverage >= 85% 2. Mypy
uv run mypy services/brief-service
# 3. Ruff
uv run ruff check services/brief-service
# 4. E2E на dev Полный цикл через curl (см. 1.4) — проходит 5. CI зелёный на push
```
## Подсказки
- **Fake llm-gateway** — критично для CI. Реальный LLM в CI = медленно, дорого, нестабильно. - 
**`@pytest.mark.slow`** — E2E тесты помечать, чтобы в быстром прогоне пропускать. - 
**`TEST_DATABASE_URL`** — отдельная БД `outreach_test`, чтобы не сносить dev-данные.
## Анти-паттерны
- ❌ Не вызывать реальный LLM в unit-тестах. - ❌ Не делать тесты, зависящие от порядка. - ❌ Не 
забывать `--cov-report=term-missing` — иначе не видно, что не покрыто. ---
## Финальная E2E-проверка Спринта 1
После всех задач проверить полный цикл: ```bash
# 0. Setup
export TENANT="<sandbox_id>" export BASE="https://brief.dev.aitler.ru"
# 1. Создать бриф
curl -sX POST $BASE/briefs \ -H "Content-Type: application/json" \ -H "X-Tenant-ID: $TENANT" \ -H 
  "Idempotency-Key: e2e-1" \ -d '{
    "text": "Мой знакомый производит гидроборты для грузовиков. Собственное производство в 
    Подмосковье, 40 сотрудников. Хочет выйти на дистрибьюторов в РФ и Казахстане.", "urls": 
    ["https://example.com"]
  }' | tee brief.json | jq .
BRIEF_ID=$(jq -r .id brief.json) echo "Brief: $BRIEF_ID"
# 2. Итеративно отвечать
for i in $(seq 0 10); do STATUS=$(curl -s -H "X-Tenant-ID: $TENANT" $BASE/briefs/$BRIEF_ID | jq -r 
  .status) echo "Iteration $i: status=$STATUS" if [ "$STATUS" = "complete" ]; then break; fi 
  PENDING=$(curl -s -H "X-Tenant-ID: $TENANT" $BASE/briefs/$BRIEF_ID | jq '[.qa_history | 
  to_entries[] | select(.value.answered_at == null) | .key][0]') if [ "$PENDING" = "null" ]; then
    echo "No pending question, stopping" break fi curl -sX POST $BASE/briefs/$BRIEF_ID/answers \ -H 
    "Content-Type: application/json" \ -H "X-Tenant-ID: $TENANT" \ -H "Idempotency-Key: 
    e2e-answer-$i" \ -d "{\"question_index\": $PENDING, \"answer\": \"Тестовый ответ $i: работаем по 
    всей России, средний чек 500k, ищем дистрибьюторов с опытом в B2B.\"}" > /dev/null
done
# 3. Проверить финал
curl -s -H "X-Tenant-ID: $TENANT" $BASE/briefs/$BRIEF_ID | jq '{status, completeness_score, 
qa_count: (.qa_history | length)}'
# Ожидание: status=complete, completeness_score >= 0.85 4. События в NATS
bash scripts/nats-cli.sh stream view BRIEFS --last 20 | grep -E 
"brief\.(created|questions_asked|completed|updated)"
# Ожидание: все четыре типа 5. LLM calls
bash scripts/psql.sh -c "SELECT task_type, count(*), sum(cost_usd) FROM llm_calls WHERE 
tenant_id='$TENANT' GROUP BY task_type;"
# Ожидание: brief_extract_v1, brief_generate_questions_v1 6. Langfuse Открыть cloud.langfuse.com → 
# трейсы с task_type brief_extract_v1, brief_generate_questions_v1 7. Idempotency
curl -sX POST $BASE/briefs \ -H "Content-Type: application/json" \ -H "X-Tenant-ID: $TENANT" \ -H 
  "Idempotency-Key: e2e-1" \ -d '{"text": "Мой знакомый производит гидроборты..."}' \ -D - | grep 
  X-Idempotent-Replay
# Ожидание: X-Idempotent-Replay: true 8. RLS
OTHER_TENANT="00000000-0000-0000-0000-000000000000" curl -s -H "X-Tenant-ID: $OTHER_TENANT" 
$BASE/briefs/$BRIEF_ID -w "%{http_code}\n" -o /dev/null
# Ожидание: 404 9. CI
git push origin develop
# Открыть GitHub Actions → все jobs ✓
``` **Если все 9 пунктов проходят — Спринт 1 закрыт.** ---
## Проверка: что я перепроверил
- [x] Порядок задач: 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6, зависимости соблюдены. - [x] Импорты и пути 
согласованы с `docs/contracts.md` и `docs/infra.md`. - [x] `contracts.Brief` не используется как 
SQLAlchemy-модель — разделены. - [x] LLM-схемы (в `llm/schemas.py`) отделены от API-схем 
(`schemas.py`) и контрактов. - [x] CompletenessScorer и MissingInfoAnalyzer — детерминированные, без 
LLM. - [x] Промпты — в отдельных файлах, версионируются через `task_type`. - [x] JSON-парсер снимает 
markdown-обёртки и находит `{...}` в тексте. - [x] Idempotency-Key везде на POST. - [x] 
`correlation_id=brief.id` во всех событиях по брифу. - [x] RLS работает: `USING` + `WITH CHECK` для 
тенант-скоупных таблиц. - [x] `website_contents` сохраняются только выжимкой (url + title). - [x] 
Fake llm-gateway для CI. - [x] E2E-тест полного цикла. - [x] `BriefStatus` расширяется `archived` 
(minor-изменение). - [x] Mypy strict, ruff, pytest — везде. - [x] Никаких `print`, `time.sleep`, 
`datetime.utcnow`. ---
## Что дальше (Спринт 2)
После закрытия Спринта 1 переходим к **ICP + sourcing** — это самый сложный и самый ценный блок 
платформы: - `icp-service`: превращает Brief в ICP с сегментами. - `sourcing-service`: ищет 
конкретные компании и контакты по ICP. - `contact-store`: хранит и дедуплицирует компании/контакты. 
Задачи Спринта 2 выдам, когда Спринт 1 будет закрыт. Формат тот же. **Что от тебя нужно сейчас:** 1. 
Разложить эти 6 задач по файлам в `docs/tasks/sprint-1/`. 2. Дать агенту-разработчику: «Начинай с 
1.1, иди по порядку, после каждой задачи проверяй acceptance criteria». 3. Сообщить мне, когда 
Спринт 1 закрыт (или если агент застрял).
Если хочешь что-то поправить в задачах сейчас — скажи. Лучше сейчас, чем потом переделывать.
