# STATE.md — где мы сейчас

> Быстрая память. Обновляется в конце каждой итерации. Единственное место, где написано «где мы».
> Последнее обновление: 2026-10-02 (iter 005)

## Сделано (Done)

### Спринт 0 — фундамент ✅
- **Инфра (dev):** Postgres 16, NATS JetStream, Redis — в docker-compose, порты на `127.0.0.1`.
- **libs/**: `common` (config, logging, context, errors, redis, health, middleware), `contracts`
  (Brief/ICP/Company/Contact/Message/Reply/Experiment + события, uuid7, UTC), `db` (async engine,
  session_scope, RLS-хелперы, mixins, UUID7-тип), `nats-client` (JetStream, publisher, subscriber,
  streams), `llm-client`.
- **services/tenant-service**: CRUD тенантов, архивация, RLS, идемпотентность, события `tenant.*`.
- **services/llm-gateway**: единая точка входа в LLM, провайдеры deepseek/mock, кэш (Redis),
  учёт вызовов (`llm_calls`), маршрутизация по модели, Langfuse (опционально).
- **Мульти-тенантность с RLS**: непривилегированная роль `outreach_app` (NOSUPERUSER, NOBYPASSRLS),
  `FORCE ROW LEVEL SECURITY`, null-safe политики через `NULLIF(current_setting('app.tenant_id', true), '')::uuid`.

### Спринт 1 — brief-service ✅
- **services/brief-service**: адаптивный intake → Brief v1.
  - `POST /briefs` (raw input: text/urls/transcript), `GET /briefs`, `GET /briefs/{id}`,
    `POST /briefs/{id}/answers`, `POST /briefs/{id}/complete`, `POST /briefs/{id}/abandon`,
    `POST /briefs/{id}/reset-question`, `DELETE /briefs/{id}`.
  - LLM-слой: клиент к llm-gateway, robust JSON-парсер, схемы валидации, версионируемые промпты
    (`brief_extract_v1`, `brief_generate_questions_v1`).
  - Детерминированный скоринг: completeness + missing_info (без LLM, веса в `scoring/constants.py`).
  - `fetcher.py` — загрузка сайтов (без JS-рендеринга).
  - События: `brief.created`, `brief.questions_asked`, `brief.updated`, `brief.completed`.
  - Миграция `0001_create_briefs` (JSONB + GIN-индексы + RLS).

### LLM: deepseek-flash + pricing + Langfuse ✅
- Модель по умолчанию — `deepseek-flash` (старые chat/reasoner удалены).
- Единый слой цен `llm_gateway/pricing.py` (peak/off-peak, cache hit/miss).
- Langfuse подключён и работает: трейсы доходят, model/usage/cost совпадают с БД. Проверка — `docs/reference/langfuse.md`.
- Миграция `0002_llm_call_tokens` (cache hit/miss, is_peak).

### Спринт 2A — contact-store ✅
- **services/contact-store**: единый источник правды по компаниям и контактам.
  - Таблицы: `companies`, `contacts`, `contact_emails`, `contact_phones`, `stoplist_entries` (RLS + FORCE на всех).
  - Fingerprint-дедуп (чистые функции): INN→domain→name (компании), email→phone→name+domain (контакты).
  - Merger: evidence по confidence, история аккумулируется, primary пересчитывается.
  - StopList: global (tenant_id NULL) + tenant-скоупный; блокирует создание контакта (409).
  - API: `POST/GET /companies`, `/companies/bulk`, `POST/GET /contacts`, `/contacts/bulk`, `/contacts/{id}/status`, `POST/GET/DELETE /stoplist`.
  - События: `company.created/updated/merged`, `contact.created/updated/merged/unsubscribed` (стрим `CONTACTS`).
- NATS: добавлен стрим `CONTACTS`, лимиты подняты (`max_file_store 8GB` через `infra/nats/nats-server.conf`).

### Спринт 2B — icp-service ✅
- **services/icp-service**: Brief → ICP (сегменты) через LLM. Изолированный LLM-сервис.
  - Таблица `icps` (payload JSONB, version, is_active, RLS+FORCE).
  - `WeightNormalizer` — детерминированная нормализация весов (сумма 1.0, компенсация округления).
  - `BriefClient` — HTTP к brief-service; `LLMClient` — к llm-gateway (retry на битый JSON, до 3 попыток).
  - Версионирование: version=max+1, старая деактивируется; activate — откат.
  - API: `POST /icps`, `GET /icps`, `GET /icps/{id}`, `GET /icps/active/by-brief/{brief_id}`, `POST /icps/{id}/revise|activate|deactivate`.
  - События: `icp.generated`, `icp.revised` (стрим BRIEFS).
- Dev-console: добавлена вкладка ICP + icp-service в health.

### Спринт 2C — sourcing-service ✅
- **services/sourcing-service**: оркестратор OSINT. ICP-сегмент → коннекторы → дедуп → LLM-нормализация → скоринг → persist в contact-store.
  - Таблицы `search_jobs`, `search_job_items` (RLS+FORCE). Версионирование не нужно.
  - Коннекторы: `serper`, `yandex_xml`, `website_parser` (httpx+bs4), `registry` (DaData-провайдер), `enricher` (Hunter-провайдер). Все — через `ConnectorRegistry`, rate-limited, дедуп по домену.
  - `Normalizer` (LLM: RawCandidate → Company/Contacts, evidence), `Scorer` (детерминированный по scoring_weights).
  - Версионирование промптов: `sourcing_normalize_candidate_v1`.
  - Фоновые задачи: `asyncio.create_task` + running_tasks, timeout, cancel, retry-failed.
  - API: `POST /searches`, `GET /searches`, `GET /searches/stats`, `GET /searches/{id}`, `POST /searches/{id}/cancel|retry-failed`.
  - События: `contacts.search_started`, `contacts.found`, `contacts.enriched` (стрим CONTACTS).
- Dev-console: вкладка «Поиски» + sourcing-service в health.

### Dev-console ✅
- `services/dev-console` — внутренний инспектор (порт 48110): здоровье сервисов, тенанты, события NATS, таблицы компаний/контактов/брифов/stop-list. Проксирует API и читает JetStream (read-only). Одна HTML-страница, без npm.
- UI: `http://<host>:48110/`, OpenAPI: `/docs`, эндпоинты `/api/*`.

### Memory layer ✅
- `AGENTS.md` (bootloader), `docs/memory/*` (PROJECT, STATE, DECISIONS, CONVENTIONS, GLOSSARY, BACKLOG),
  `docs/reference/pricing.md`, `docs/reference/scoring.md`, журнал `docs/memory/iterations/`.

## В работе (In progress)
- (нет — всё запланированное на iter 001 закрыто)

## Далее (Next)
- **Спринт 2**: `icp-service` (Brief → ICP с сегментами), `sourcing-service` (OSINT), `contact-store`.
- Заполнить ключи Langfuse и проверить трейсы.
- Проверить/завести stage и prod окружения.

## Блокеры
- Нет (на момент обновления).

## Карта портов (dev)

| Сервис | Порт (host) | Внутри |
|---|---|---|
| tenant-service | 48100 | 8000 |
| llm-gateway | 48101 | 8000 |
| brief-service | 48102 | 8000 |
| contact-store | 48103 | 8000 |
| icp-service | 48104 | 8000 |
| sourcing-service | 48105 | 8000 |
| dev-console | 48110 | 8000 |
| Postgres | 48532 | 5432 |
| NATS client | 48222 | 4222 |
| NATS monitor | 48220 | 8222 |
| Redis | 48633 | 6379 |

## Как поднять/проверить (dev)

    bash scripts/bootstrap.sh          # с нуля
    bash scripts/healthcheck.sh        # проверить все сервисы
    bash scripts/migrate.sh            # применить миграции
    uv run pytest -q                   # unit-тесты
    uv run pytest -m integration -q    # интеграционные (нужен запущенный стек)
