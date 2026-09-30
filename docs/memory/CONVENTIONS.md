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
    api/                 # routes.py, deps.py
  tests/
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
