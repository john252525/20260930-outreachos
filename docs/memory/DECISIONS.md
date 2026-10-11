# DECISIONS.md — Architecture Decision Records

> ADR-стиль: почему сделали так, а не иначе. Чтобы агент через N обнулений не предлагал отвергнутое.

## ADR-001: Монорепа на uv workspaces

**Контекст:** много сервисов и общих библиотек, которые должны переиспользоваться без публикации в приватный PyPI.
**Решение:** одна монорепа, `uv` workspaces, `[tool.uv.sources]` с `workspace = true`. Либы `common`/`contracts`/`db`/`nats-client`/`llm-client`.
**Последствия:** один `uv.lock`; сборка каждого сервиса в отдельный Docker-образ через `uv sync --package <svc> --no-editable`.

## ADR-002: NATS JetStream как событийная шина (а не Redis Streams)

**Контекст:** нужна надёжная асинхронная шина с персистентностью и переигрыванием.
**Решение:** NATS JetStream (pull-consumers, durable, ack/nack, retention per stream).
**Последствия:** стримы `TENANTS`, `BRIEFS`, `LLM_CALLS`, `SYSTEM`; дедупликация через `Nats-Msg-Id`. Redis оставлен для кэша/идемпотентности/rate-limit.

## ADR-003: Мульти-тенантность через `tenant_id` + Row-Level Security

**Контекст:** проектов может быть сотни, нужна изоляция данных и защита от «забыл WHERE tenant_id».
**Решение:** одна БД, у каждой бизнес-таблицы `tenant_id` + RLS-политики. Сервисы ходят под **непривилегированной ролью** `outreach_app` (NOSUPERUSER, NOBYPASSRLS).
**Последствия:**
- Владелец таблиц (суперюзер `outreach`) применяет миграции; приложение — под `outreach_app`.
- На таблицах `ENABLE` **и** `FORCE ROW LEVEL SECURITY` (иначе владелец/суперюзер обходят RLS).
- Политики null-safe: `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid` (после commit GUC становится пустой строкой `''`).
- `SET LOCAL app.tenant_id` ставится в начале транзакции.

## ADR-004: `INSERT ... RETURNING` и RLS при создании тенанта

**Контекст:** SQLAlchemy всегда добавляет `RETURNING` для server-defaults. `RETURNING` требует, чтобы новая строка прошла **SELECT-политику** (`USING`), а `app.tenant_id` при создании ещё не задан.
**Решение:** при создании тенанта явно сгенерировать `id` (UUID v7) и поставить `set_tenant_context(session, tenant.id)` до INSERT. У политики `tenants` — `WITH CHECK (true)`.
**Последствия:** тенант «видит себя» в момент создания.

## ADR-005: Идемпотентность через `Idempotency-Key` + Redis

**Контекст:** агенты/клиенты ретраят POST-запросы.
**Решение:** middleware `IdempotencyMiddleware`, ключ `idem:<tenant>:<key>`, TTL 24ч, реплей сохранённого ответа с заголовком `X-Idempotent-Replay: true`.
**Последствия:** клиент обязан слать уникальный `Idempotency-Key`; повторный запрос с тем же ключом вернёт кэш (важно в тестах — не переиспользовать ключ между разными вызовами).

## ADR-006: Все вызовы LLM — через `llm-gateway`

**Контекст:** нельзя, чтобы каждый сервис имел свой ключ, свою обёртку и свою логику ретраев/учёта.
**Решение:** единая точка `llm-gateway`. Сервисы шлют `POST /v1/complete` c `X-Tenant-ID`, `task_type`, `json_mode`.
**Последствия:** учёт токенов/стоимости в одном месте (`llm_calls`), кэш по хэшу промпта (включая провайдера — чтобы не смешивать ответы разных моделей), публикация `llm.called`.

## ADR-007: Верисионирование промптов через `task_type`

**Контекст:** нужен A/B по промптам и разбор метрик по версиям.
**Решение:** `task_type` включает версию: `brief_extract_v1`, `brief_generate_questions_v1`. Промпты — в отдельных файлах (`llm/prompts/`).
**Последствия:** при изменении промпта — поднять версию, старые вызовы остаются различимыми в `llm_calls`.

## ADR-008: Детерминированный скоринг брифа (без LLM)

**Контекст:** «насколько полон бриф» и «чего не хватает» — это арифметика, а не генерация. LLM тут дорог и нестабилен.
**Решение:** `completeness` и `missing_info` считаются кодом по весам из `scoring/constants.py`. LLM используется только для генерации вопросов.
**Последствия:** предсказуемость, ноль токенов на скоринг, легко тестировать. Детали — `docs/reference/scoring.md`.

## ADR-009: Контракты, API-схемы и LLM-схемы — разные модели

**Контекст:** смешение Pydantic-контракта и ORM/API ведёт к циклическим зависимостям и протечке слоёв.
**Решение:**
- `libs/contracts` — то, что ходит между сервисами (версионируется, `extra="ignore"`).
- `services/*/schemas.py` — то, что принимает/отдаёт HTTP.
- `services/*/llm/schemas.py` — то, чем валидируем ответ LLM.
- SQLAlchemy-модель — «сырая» (JSONB), контракт — «умный».
**Последствия:** конвертация явная; никаких ORM-моделей в контрактах.

## ADR-010: Модель LLM по умолчанию — `deepseek-flash`

**Контекст:** старые `deepseek-chat`/`deepseek-reasoner` устарели (сентябрь 2026).
**Решение:** дефолт везде — `deepseek-flash`. Роутинг в llm-gateway по префиксу `deepseek-*` → провайдер deepseek.
**Последствия:** цены только на `deepseek-flash` (см. `docs/reference/pricing.md`); учёт стоимости — в едином слое.

## ADR-011: Память агента в `docs/memory/` + `AGENTS.md`

**Контекст:** агент stateless, контекст обнуляется, нужно быстро восстанавливать «где мы».
**Решение:** три горизонта памяти — Cold (PROJECT/DECISIONS/CONVENTIONS), Warm (STATE/BACKLOG), Hot/append-only (iterations/). `AGENTS.md` — точка входа.
**Последствия:** STATE.md — единственный источник «где мы»; в конце итерации обязательное обновление.

## ADR-012: Явный лимит хранилища JetStream

**Контекст:** NATS JetStream бронирует место не по факту данных, а по сумме `max_bytes`
всех стримов (`reserved_storage`). У нас 5 стримов с потолками 256-512 MiB каждый →
суммарно ~1.6 GiB «брони». Дефолтный общий пул (`max_file_store`) был ~1.2 GiB, поэтому
добавление стрима `CONTACTS` упало с `insufficient storage resources available`
(при фактических данных < 1 MiB — это не проблема объёма, а проблема конфигурации).

**Решение:** задать общий пул явно через конфиг-файл `infra/nats/nats-server.conf`:
`max_file_store: 8GB`, `max_memory_store: 512MB`. Пробросить через `command: -c ...` в compose.

**Последствия:**
- Пул (8 GiB) ≫ сумма броней стримов (~1.6 GiB) — запас есть.
- Флаги `--js-max-file-store`/`--js-max-memory` в CLI nats-server НЕ существуют — только конфиг-файл.
- При добавлении новых стримов проверять: сумма их `max_bytes` не должна превышать `max_file_store`.
- Мониторинг: `curl http://127.0.0.1:$NATS_MONITOR_PORT/jsz` → `reserved_storage` vs `config.max_storage`.

## ADR-013: Пайплайн сообщений собран из трёх сервисов (composer / review / sender)

**Контекст:** генерация, ревью и отправка — разные по природе (генерация stateless, ревью stateful, отправка рискованна для репутации).
**Решение:** три отдельных сервиса, связанные событиями NATS:
composer (`message.drafted`) → review-queue (`message.approved`/`message.rejected`) → sender (`message.sent`/`message.bounced`).
**Последствия:**
- Human-in-the-loop по умолчанию: `sender-email` отправляет только сообщения в статусе `approved`.
- Авто-отправка — это флаг (по ТЗ включается после 500 писем с reply rate > baseline).
- Статус Message живёт в composer (`draft → approved → sent/rejected/failed`), обновляется через `PATCH /messages/{id}`.

## ADR-014: `sender-email` — только dry-run на dev, per-employee ящик

**Контекст:** ошибочная отправка сжигает репутацию домена за дни. Нужен безопасный режим и правильная модель отправителя.
**Решение:**
- На dev `SENDER_DRY_RUN=true`: письмо не уходит, но SendAttempt и событие пишутся как обычно (`provider_message_id = dry-run-<id>`).
- Отправляем с **личного ящика сотрудника** (SMTP/IMAP), не с общего `sales@` (deliverability + юридика + reply-detection).
- Пароли ящиков шифруются **Fernet** (`SENDER_ENCRYPTION_KEY`), в БД — только шифротекст.
- Ramp-up (warm-up) обязателен: `WarmUpScheduler` поднимает лимиты по дням (день 1: 5/день, 2/час … день 30: 50/10). Счётчики — в Redis.
- Обязательны заголовки `List-Unsubscribe` + `List-Unsubscribe-Post: One-Click`.
**Последствия:** реальная отправка включается явно; тестовый ящик с `smtp_username="dry-run"` верифицируется без реального SMTP.

## ADR-015: dev-console — не продуктовый UI, а тонкий инспектор

**Контекст:** нужна прозрачность (что летит в NATS, что в таблицах), без вложений в продуктовый фронт.
**Решение:** один сервис `dev-console` (vanilla HTML, без npm), проксирует API сервисов и читает JetStream read-only.
**Последствия:**
- Список всех тенантов через API невозможен (RLS), поэтому dev-console читает тенантов через **read-only admin-DSN** напрямую из Postgres — осознанное исключение только для инструмента.
- Вкладки: Сервисы, События NATS, Компании/Контакты/Брифы/ICP/Поиски/Письма/Ревью/Stop-list.

## ADR-016: Сериализация сущностей contact-store — «разворачивание payload»

**Контекст:** `contact-store` хранит поля Company/Contact в JSONB-колонке `payload`, а верхнеуровневыми держит только «горячие» поля (`id`, `status`, `company_id`, ...).
**Решение:** потребители (composer и др.) разворачивают entity хелпером `_unwrap`: `{**payload, **top-level}`.
**Последствия:** при чтении контакта из contact-store в composer обязателен `_unwrap`, иначе поля (`full_name`, `emails`, ...) окажутся пустыми. Это уже ловили (recipient_snapshot был пустым).

## ADR-017: analytics-service читает через admin-DSN, изоляция — явным фильтром

**Контекст:** `analytics-service` считает метрики по данным других сервисов (`messages`, `send_attempts`,
`replies`, `search_jobs`, `contacts`) и materialized views в схеме `analytics`. Приложение ходит под ролью
`outreach_app` (NOBYPASSRLS). Но:
- `REFRESH MATERIALIZED VIEW` под app-ролью наполняет MV только теми строками, что видны при текущем
  `app.tenant_id` (без него — пусто).
- MV — не таблицы, RLS-политики на них не навешиваются.
- Alert engine должен перечислять всех тенантов.

**Решение:**
- Миграции и `REFRESH` выполняются владельцем (`outreach`) — MV строятся по всем тенантам.
- `analytics-service` использует `DATABASE_URL_ADMIN` (владелец) для чтения MV и прямых запросов;
  tenant-изоляция обеспечивается **явным `WHERE tenant_id = :tid`** в каждом запросе.
- Сервис ничего не пишет в чужие таблицы (read-only по контракту; никаких INSERT/UPDATE — только палитра
  SELECT и `REFRESH`).

**Последствия:**
- Это осознанное исключение из RLS — как dev-console (ADR-015), но для аналитики.
- Все API-запросы обязаны передавать `tenant_id`; функции репозитория без tenant-фильтра запрещены.
- Кэш метрик в Redis ключуется по `tenant_id`.

## ADR-018: MV refresh — plain REFRESH (не CONCURRENTLY) на dev

**Контекст:** materialized views в схеме `analytics` имеют уникальные индексы для быстрого
апдейта. Однако часть индексов — expression-индексы (`COALESCE(template_id, '')`), а
`REFRESH MATERIALIZED VIEW CONCURRENTLY` требует уникальный индекс **без** выражений.
На таких MV `CONCURRENTLY` падает с ошибкой.

**Решение:** `MVRefresher` использует обычный `REFRESH MATERIALIZED VIEW` (блокирует чтение
на время апдейта). На dev объёмы малы, интервал 300с — блокировка незаметна. Для prod можно
перейти на `CONCURRENTLY`, заменив COALESCE-индексы на индексы с materialized-колонками.

**Последствия:** апдейт MV ненадолго блокирует дашборд-запросы; приемлемо для dev.

