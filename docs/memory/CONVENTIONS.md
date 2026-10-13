# CONVENTIONS.md — как писать код в этом репо

> Чтобы агент не переизобретал стиль и паттерны.

## Python

- Python **3.12**, async-first. Никаких блокирующих вызовов в async (используй `asyncio.sleep`, `httpx.AsyncClient`).
- **Pydantic v2** для схем/контрактов. `model_config = ConfigDict(extra="ignore")` для forward-compat.
- Типизация обязательна. **`mypy --strict`** должен быть зелёным.
- Форматирование — **ruff** (`ruff check` + `ruff format`), line-length 100.

## Запрещено

- `print()` → только `structlog`.
- `time.sleep()` → только `asyncio.sleep()`.
- `datetime.utcnow()` → только `datetime.now(timezone.utc)`. Timestamps — aware UTC.
- `dict`/`list` без параметров типа в аннотациях (mypy strict): `dict[str, Any]`, `list[str]`.
- `isinstance(x, dict[str, Any])` — так нельзя, только `isinstance(x, dict)`.

## Идентификаторы и время

- **UUID v7** везде: `common.uuid7()` или `db.types.generate_uuid7()`.
- Timestamps — RFC3339 UTC с суффиксом `Z` в сериализации.

## Структура сервиса

```
services/<name>/
  pyproject.toml         # uv-пакет, зависимости от libs
  Dockerfile             # multi-stage, uv, non-root
  alembic.ini
  migrations/            # env.py + versions/
  src/<pkg>/
    __init__.py
    main.py              # FastAPI app + lifespan (init_engine, init_redis, NATS, LLMClient)
    config.py            # Settings(BaseServiceSettings)
    models.py            # SQLAlchemy (raw)
    schemas.py           # API-схемы (отдельно от contracts)
    repository.py        # доступ к данным
    service.py           # бизнес-логика
    events.py            # публикация NATS-событий
    clients/             # httpx-клиенты к другим сервисам
    api/                 # routes.py, deps.py
  tests/

apps/web/                # Next.js UI + BFF (npm-мир, pnpm; НЕ uv)
  src/app/               # App Router; (app)/* — защищённые, (auth)/login
  src/app/api/proxy/     # BFF: /api/proxy/<service>/<path>
  src/lib/               # auth (Auth.js), api-client, hooks
  middleware.ts          # auth-guard
```

## Паттерны сервиса

- **lifespan** инициализирует `init_engine`, `init_redis`, `NATSConnection`, `Publisher`, и (если нужно) `LLMClient`; в `finally` — закрывает всё.
- **Middleware** (порядок важен): `TraceMiddleware` → `TenantMiddleware` → `IdempotencyMiddleware`. Обработчики ошибок: `AppError` → JSON, `Exception` → 500.
- **DI**: `get_service` — `async with session.begin()`, ставит `set_tenant_context(tenant_id)` если есть, yield-ит сервис.
- **Транзакции**: коммит делает `session_scope`/`session.begin()` в DI. Сервис не коммитит сам.
- **События** публикуются после успешного flush/commit. `correlation_id` — id сущности (например, brief).
- **flush + refresh**: после изменения ORM-объекта с `onupdate=func.now()` делаем `flush()` и `refresh()`, иначе Pydantic читает expired-атрибут вне async-контекста (`MissingGreenlet`).

## Ошибки

- Доменные ошибки — наследники `common.errors.AppError` (`NotFoundError` 404, `ConflictError` 409, `ValidationError` 422).
- Уникальные нарушения БД (например, slug) — ловить `IntegrityError` и маппить в `ConflictError` (RLS может скрывать чужие строки от pre-check).
- Все ошибки логируются структурированно (`structlog`), `unhandled_error` — с трейсбеком.

## Тесты

- `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), `--import-mode=importlib`.
- Unit-тесты рядом с либой/сервисом (`tests/`). Интеграционные — маркер `@pytest.mark.integration` (по умолчанию отключены через `-m 'not integration'`).
- Интеграционные тесты ходят по HTTP к запущенному dev-стеку.
- Не вызывать реальный LLM в тестах — есть `mock`-провайдер и `tests/fake_llm_gateway.py`.

## Env / секреты

- Секреты — только в `.env` (gitignored). `.env.example` — шаблон без секретов.
- Названия переменных: `SERVICE_*`, `POSTGRES_*`, `NATS_*`, `REDIS_*`, `DEEPSEEK_*`, `LANGFUSE_*`, `BRIEF_*`.

## Коммиты

- Сообщение: `iter NNN: <summary>` (см. `AGENTS.md`).

## Межсервисные паттерны (Спринты 2C-3)

- **Сервис не ходит в чужую БД** — только HTTP + NATS. Клиенты к другим сервисам — в `clients/` (httpx).
- **`contact-store` entity:** поля Company/Contact лежат в `payload` (JSONB), верхнеуровнево — только «горячие»
  (`id`, `status`, `company_id`, ...). Потребители обязаны «разворачивать»: `{**payload, **top-level}` (см. ADR-016).
- **`flush + refresh`** после мутации ORM-объекта с `onupdate=func.now()`: `flush()` затем `refresh()`, иначе
  Pydantic читает expired-атрибут вне async-greenlet (`MissingGreenlet`). Паттерн `_flush(obj)` в сервисах.
- **NATS-подписки:** `Subscriber` с durable consumer, pull-subscribe. Обработчик получает `EventEnvelope`,
  где `envelope.payload` — **Pydantic-модель**, не dict (обращаться через атрибуты: `payload.message.id`).
- **События публикуются после flush**, `correlation_id` = id сущности. Регистрация новых subjects — в
  `libs/nats-client/.../subjects.py` + payload-модель в `libs/contracts/.../events.py` (+ стрим в `streams.py`).
- **LLM JSON:** ответ LLM валидируется через tolerant-базу (`LLMSchemaBase`): `null` для str/list → дефолт.
  Битый JSON/схема → retry (до 3 попыток) + `AppError` (502), не 500.
- **Фоновые задачи:** `asyncio.create_task` + хранение ссылок в `running_tasks` (иначе GC убьёт); своя session.
- **Идемпотентность исходящих:** `Idempotency-Key` на POST/PATCH к другим сервисам (напр. `sourcing:{job}:company:{item}`).
- **Схемы ответов-списков** (`*Summary`) нужны `from_attributes=True`, если валидируются из ORM-объектов.

## Паттерны Спринтов 4-6

- **Материализованные представления (`analytics`):** схема `analytics` + MV; REFRESH — под owner-ролью
  (`REFRESH` не сработает под RLS-ролью). См. ADR-017/018.
- **Cross-tenant листинг** (retry worker, evaluate-loop, alert engine): owner/admin-DSN
  (`DATABASE_URL_ADMIN`), изоляция — явным `WHERE tenant_id` (ADR-017).
- **NATS-subscriber:** `deliver_policy` настраиваем (`NEW` для «живых» оркестраторов, `ALL` для
  тех, кто должен видеть историю). Обработчик получает `EventEnvelope` с Pydantic-payload.
- **Orchestrator handlers:** сами открывают session после `envelope.tenant_id`; проверяют
  `flow.status == "running"`; идемпотентны (reconciliation при повторной обработке); 4xx — терминально,
  5xx/transport — retry (см. `is_retryable`). `flow_steps.input_data` хранит `original_event_type`/`original_event_payload`.
- **Per-tenant settings:** читать через `TenantClient.get_settings` (кэш Redis 300с); дефолты — в коде.
  Флаги `auto_*` и channel-enable проверять из настроек, не из глобального env.
- **BFF (Web UI):** браузер → только `/api/proxy/<service>/<path>` (Next.js route handler). Он
  подставляет `X-Tenant-ID`/`X-User-Id` из серверной сессии и `Authorization: Bearer SERVICE_TOKEN`.
  Прямые вызовы микросервисов из браузера запрещены.
- **Service auth:** `common.auth.require_service_token` (opt-in: no-op если `SERVICE_TOKEN` не задан).
- **Секреты каналов:** Telegram/LinkedIn — Fernet (`*_ENCRYPTION_KEY`); в БД только шифротекст.
- **Опальные каналы (Telegram/LinkedIn):** double opt-in, consent/connection-check, warm-up, dry-run,
  captcha/ban → ручное вмешательство, FloodWait-обработка.
