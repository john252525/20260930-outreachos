# STATE.md — где мы сейчас

> Быстрая память. Обновляется в конце каждой итерации. Единственное место, где написано «где мы».
> Последнее обновление: 2026-10-12 (iter 012 — Спринт 6: Web UI + LinkedIn + per-tenant settings + multi-region docs)

## TL;DR для нового агента

- Платформа **Outreach OS** — мульти-тенантный outreach из API-first микросервисов.
- **Спринты 0–6 закрыты** (0, 1, 2A-C, 3A-C, 4A-C, 5A-C, 6A-D). Система самоуправляемая
  (brief → ICP → sourcing → drafts → review → send → reply → analytics → A/B → auto-revision),
  **3 канала** (email + Telegram + LinkedIn) и **Web UI** (Next.js).
  Следующий — **Спринт 7** (WhatsApp, bandit, ML-скоринг, users+roles, audit log).
- Полный цикл работает end-to-end: Brief → ICP → Sourcing → Composer → Review → Sender (dry-run).
- Стек: Python 3.12 / FastAPI / Postgres+RLS / NATS JetStream / Redis / uv workspaces / Docker Compose.
- Всё поднимается через `bash scripts/bootstrap.sh`; проверка — `bash scripts/healthcheck.sh`.
- **Web UI (продукт):** `http://<host>:48117/`. Dev-логин: `sergey@example.com` / `outreach`
  (в `.env` хранится bcrypt-хеш в `AUTH_USERS`; пользователи — пока в env, в БД — Спринт 7).
- Фронт-инспектор: `http://<host>:48110/` (dev-console).

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
- **Мульти-тенантность с RLS**: роль `outreach_app` (NOSUPERUSER, NOBYPASSRLS),
  `FORCE ROW LEVEL SECURITY`, null-safe политики через `NULLIF(current_setting('app.tenant_id', true), '')::uuid`.

### Спринт 1 — brief-service ✅
- Адаптивный intake → Brief v1. Endpoints: `POST/GET /briefs`, `GET /briefs/{id}`,
  `POST /briefs/{id}/answers|complete|abandon|reset-question`, `DELETE /briefs/{id}`.
- LLM-промпты `brief_extract_v1`, `brief_generate_questions_v1`; детерминированный completeness + missing_info.
- События: `brief.created`, `brief.questions_asked`, `brief.updated`, `brief.completed`.

### LLM: deepseek-flash + pricing + Langfuse ✅
- Модель по умолчанию — `deepseek-flash` (старые chat/reasoner удалены).
- Единый слой цен `llm_gateway/pricing.py` (peak/off-peak, cache hit/miss).
- Langfuse подключён: трейсы доходят, model/usage/cost совпадают с БД → `docs/reference/langfuse.md`.

### Спринт 2A — contact-store ✅
- Таблицы `companies`, `contacts`, `contact_emails`, `contact_phones`, `stoplist_entries` (RLS + FORCE).
- Fingerprint-дедуп (INN→domain→name; email→phone→name+domain), Merger (evidence по confidence),
  StopList (global + tenant). API: companies/contacts CRUD + bulk + status, stoplist.
- События: `company.*`, `contact.*` (стрим `CONTACTS`).

### Спринт 2B — icp-service ✅
- Brief → ICP (сегменты) через LLM. Таблица `icps` (payload JSONB, version, is_active).
- `WeightNormalizer` (сумма 1.0, компенсация округления). Версионирование + откат.
- API: `POST/GET /icps`, `/icps/{id}`, `/icps/active/by-brief/{id}`, `POST /icps/{id}/revise|activate|deactivate`.
- События: `icp.generated`, `icp.revised`.

### Спринт 2C — sourcing-service ✅
- Оркестратор OSINT: ICP-сегмент → коннекторы → дедуп → LLM-нормализация → скоринг → contact-store.
- Таблицы `search_jobs`, `search_job_items` (RLS+FORCE).
- Коннекторы: `serper`, `yandex_xml`, `website_parser` (httpx+bs4), `registry` (DaData), `enricher` (Hunter).
- API: `POST/GET /searches`, `/searches/stats`, `/searches/{id}`, `POST /searches/{id}/cancel|retry-failed`.
- События: `contacts.search_started`, `contacts.found`, `contacts.enriched`.

### Спринт 3A — composer-service ✅
- Генерация писем. TemplateRegistry (`email_cold_outreach_v1`, `email_followup_v1`),
  Personalizer (LLM), FactChecker (детерминированный, evidence/factual_claims).
- Таблица `messages` (RLS+FORCE). Endpoints: `POST /messages`, `GET /messages`, `GET/PATCH /messages/{id}`.
- Событие `message.drafted`.

### Спринт 3B — review-queue ✅
- Human-in-the-loop. Подписка на `message.drafted.*` (durable consumer) → ReviewItem (priority high при warnings/hypotheses).
- Endpoints: list, get, `approve/reject/edit/assign`, bulk-approve. Обновляет Message в composer через PATCH.
- События `message.approved`, `message.rejected`.

### Спринт 3C — sender-email ✅
- Отправка (dev: dry-run). `sender_accounts` (пароли шифруются Fernet), `send_attempts`.
- SMTP-клиент (aiosmtplib), ramp-up/warm-up (Redis-счётчики), AccountSelector, stop-list, List-Unsubscribe.
- Подписка на `message.approved.*` → отправка → `message.sent`.
- Endpoints: accounts CRUD + `verify|pause|resume`.


### Спринт 4 — analytics + reply-classifier + A/B ✅
- **4A `reply-classifier`** (порт 48111): таблица `replies` (RLS+FORCE, уникальный индекс
  `(tenant_id, message_id, from_email)` для дедупа). `CompositeClassifier` = `RuleBasedClassifier`
  (auto-reply / OOO / unsubscribe / wrong_person / not_interested / positive) → `LLMClassifier`
  (`task_type=reply_classify_v1`, temperature 0.1, JSON-схема). Подписка на `reply.received.*`
  (BRIEFS, durable `reply-classifier`). API: `GET /replies`, `GET /replies/{id}`,
  `POST /replies/{id}/handle`, `POST /replies/{id}/reclassify`. Событие `reply.classified`.
  Автоотписка контакта при `unsubscribe`; `replied_positive`/`last_reply_at` при позитиве.
  `status=needs_review` при confidence < `REPLY_MIN_CONFIDENCE` (0.6).
- **4B `analytics-service`** (порт 48112): схема `analytics` + 5 MATERIALIZED VIEW
  (`mv_daily_message_metrics`, `mv_daily_reply_metrics`, `mv_daily_sender_metrics`,
  `mv_daily_sourcing_metrics`, `mv_funnel`). Читает через owner-DSN (`DATABASE_URL_ADMIN`,
  ADR-017), изоляция — явным `WHERE tenant_id`. `MVRefresher` (раз в 300с) + `AlertEngine`
  (раз в час, только при выборке ≥50/≥20) → событие `analytics.alert`. API:
  `/analytics/overview|funnel|by-template|by-sender|reply-categories|sourcing|segments|daily|
  experiment-variants`. Кэш в Redis 60с.
- **4C `experiments-service`** (порт 48113): таблица `experiments` (RLS+FORCE, unique
  `(tenant_id, name)`). `VariantAssigner` (детерминированный sha256-хеш `exp:contact`),
  `StatsEngine` (two-proportion z-test + Wilson CI + Bonferroni + MDE). API:
  `POST/GET /experiments`, `GET /experiments/{id}`, `POST /experiments/{id}/{start|pause|evaluate|assign}`.
  События `experiment.created`, `experiment.variant_won`. Авто-evaluate раз в час.
- **Интеграция:** composer при `experiment_id` запрашивает `assign` и берёт `template_id` варианта;
  `experiment` пишется в `personalization` сообщения. `segment_id`/`icp_id` добавлены в `personalization`.
- **Response-контракт `reply.received` расширен** (`from_email/from_name/subject/body/received_at/
  in_reply_to/references/message_id_header`) — backward-compatible (поля опциональны).
- **New subject** `analytics.alert` (стрим BRIEFS); bootstrap NATS теперь идемпотентно
  до-писывает subjects существующих стримов (`update_stream`).
- **contact-store:** новый endpoint `PATCH /contacts/{id}/outreach-history`.
- **composer:** `json_utils` теперь `json.loads(..., strict=False)` (устойчивость к literal
  control-characters в LLM-JSON).
- **dev-console:** вкладки Ответы/Эксперименты/Аналитика; рабочий Swagger-прокси `/docs/{service}`.

### Побочные фиксы Спринта 4
- `libs/nats-client`: идемпотентное обновление subjects стрима при старте.
- `libs/contracts`: `ReplySnapshot` расширен; `AnalyticsAlertPayload`; `EVENT_PAYLOAD_MAP`.
- `libs/nats-client/subjects.py`: `ANALYTICS_ALERT`.


### Спринт 5 — orchestrator + auto-revision + telegram ✅
- **5A `orchestrator`** (порт 48114): event-driven дирижёр. Таблицы `flows` / `flow_steps` (RLS+FORCE).
  `EventRouter` + handlers (brief.completed → ICP; icp.generated → sourcing; contacts.found →
  draft/pause; message.* observability; reply.received; analytics.alert → auto-revision).
  `RetryWorker` (exponential backoff, reconciliation, admin-DSN для cross-tenant — ADR-017).
  `/metrics` (Prometheus), API: `/flows*`, `/stats`, `trigger-draft`, pause/resume/cancel.
  События `flow.started|step_completed|completed|failed` (стрим FLOWS).
- **5B `auto-revision`** (порт 48115): таблица `revisions`. `MetricsAnalyzer` → `LLMAdvisor`
  (`auto_revision_diagnose_v1`) → `TemplateRevisor` (`auto_revision_revise_v1`). Human-in-the-loop:
  `POST /revisions/propose`, `approve` (создаёт `template_overrides` в composer + эксперимент
  через experiments-service), `reject`. События `revision.proposed|approved|rejected`.
  В composer добавлена таблица `template_overrides` (data-driven промпты, `{{ var }}`-подстановка);
  composer применяет активный override при draft.
- **5C `telegram-sender`** (порт 48116): таблицы `telegram_accounts` / `telegram_send_attempts`
  (RLS+FORCE). Bot API (httpx) + MTProto (Telethon, lazy). Fernet-шифрование секретов.
  Жёсткий warm-up (3→30/день), FloodWait-обработка, **consent-гейт** (не шлём без messenger_opt_in
  или prior reply). Подписка на `message.approved.*` (channel=telegram). Dry-run по умолчанию.
- **Новые subjects:** `flow.*`, `revision.*` (стрим FLOWS); bootstrap NATS до-писывает стримы.
- **dev-console:** вкладки Флоу / Ревизии / Telegram; Swagger-прокси `/docs/{service}`.


### Спринт 6 — Web UI + LinkedIn + per-tenant settings + multi-region docs ✅
- **6A Web UI** (`apps/web`, Next.js 15 App Router, порт 48117): Auth.js (credentials+JWT,
  `AUTH_USERS` в env), BFF-прокси `/api/proxy/<service>/<path>` (SERVICE_TOKEN не утекает в браузер).
  Страницы: login, dashboard (KPI+funnel+flows), reviews (+detail, approve/reject/edit),
  flows (+detail, pause/resume/cancel), analytics (overview/categories/senders/templates),
  experiments, revisions (approve), messages, settings. Tailwind + shadcn-подобные UI-компоненты.
- **6B `linkedin-sender`** (порт 48118): таблицы `linkedin_accounts` / `linkedin_send_attempts`
  (RLS+FORCE). Fernet-шифрование, residential-proxy, warm-up (5→20/день), `linkedin-api` (lazy) с
  dry-run, captcha→ручное решение (`/solve-captcha`), ban→событие `linkedin.ban_detected`.
  **Двойной opt-in:** глобальный `LINKEDIN_ENABLED` + per-tenant `linkedin_enabled`;
  **connection check** (`messengers.linkedin.is_connected`). Dry-run по умолчанию.
- **6C Per-tenant settings**: таблица `tenant_settings` в tenant-service (RLS, авто-создание при
  создании tenant). API `GET/PATCH /tenants/{id}/settings`. Кэш в Redis (5 мин).
  Интегрировано: orchestrator (флаги auto_* + sources/limits), composer (channel enabled),
  linkedin-sender (opt-in). `require_service_token` в `libs/common` (opt-in enforcement).
- **6D Multi-region groundwork**: `docs/multi-region.md` + `docs/runbook-multi-region.md`
  (модель данных, репликация, роутинг, миграция tenant, failover). Реализация — Спринт 8.
- **dev-console:** вкладка LinkedIn; BFF-совместимые data-эндпоинты для settings/telegram/linkedin.

### Dev-console ✅
- `services/dev-console` (порт 48110): здоровье сервисов, тенанты, события NATS, таблицы
  компаний/контактов/брифов/ICP/поисков/писем/ревью/stop-list. Проксирует API + читает JetStream (read-only).
- UI: `http://<host>:48110/`. Тенант-лист — через read-only admin-DSN (RLS это требует).

### Memory layer ✅
- `AGENTS.md` (bootloader) + `docs/memory/*` + `docs/reference/*` + `docs/memory/iterations/`.

## В работе (In progress)
- (нет)

## Далее (Next)
- **Спринт 7**: WhatsApp sender, multi-armed bandit, ML-скоринг, users+roles в БД, campaign entity, audit log.
- **Спринт 8**: реализация multi-region (см. `docs/multi-region.md`).
- Позже: Telegram/WhatsApp sender (3D), LinkedIn (3E), зарубежные OSINT-источники (2D), stage/prod окружения.

## Блокеры
- Нет на момент обновления.
- **Внимание (dev-среда):** VPS с памятью/диском «впритык» (~3.7 ГБ RAM, диск часто >80%). Сборка образов
  иногда таймаутит — помогает `docker builder prune -f`. Чужие контейнеры на сервере НЕ трогать.

## Карта портов (dev)

| Сервис | Порт (host) | Внутри |
|---|---|---|
| tenant-service | 48100 | 8000 |
| llm-gateway | 48101 | 8000 |
| brief-service | 48102 | 8000 |
| contact-store | 48103 | 8000 |
| icp-service | 48104 | 8000 |
| sourcing-service | 48105 | 8000 |
| composer-service | 48106 | 8000 |
| review-queue | 48107 | 8000 |
| sender-email | 48108 | 8000 |
| reply-classifier | 48111 | 8000 |
| analytics-service | 48112 | 8000 |
| experiments-service | 48113 | 8000 |
| orchestrator | 48114 | 8000 |
| auto-revision | 48115 | 8000 |
| telegram-sender | 48116 | 8000 |
| web (Next.js) | 48117 | 3000 |
| linkedin-sender | 48118 | 8000 |
| dev-console | 48110 | 8000 |
| Postgres | 48532 | 5432 |
| NATS client | 48222 | 4222 |
| NATS monitor | 48220 | 8222 |
| Redis | 48633 | 6379 |

## Как поднять/проверить (dev)

    export PATH="$PWD/.tools:$PATH"   # локальный uv
    bash scripts/bootstrap.sh          # с нуля
    bash scripts/healthcheck.sh        # проверить все сервисы
    bash scripts/migrate.sh            # применить миграции
    uv run pytest -q                   # unit-тесты
    uv run pytest -m integration -q    # интеграционные (нужен запущенный стек)

## Полезные факты для быстрого старта

- **Все LLM-вызовы — только через `llm-gateway`** (`POST /v1/complete`), не напрямую в DeepSeek.
- **Сервисы не ходят друг к другу в БД** — только HTTP + NATS.
- **Device-режимы (dry-run):** `SENDER_DRY_RUN`, `TELEGRAM_DRY_RUN`, `LINKEDIN_DRY_RUN` — true; реально не отправляем.
- **Секреты-ключи (Fernet):** `SENDER_ENCRYPTION_KEY`, `TELEGRAM_ENCRYPTION_KEY`, `LINKEDIN_ENCRYPTION_KEY`, `NEXTAUTH_SECRET`, `WEB_SERVICE_TOKEN`.
- **Опальные каналы:** `LINKEDIN_ENABLED=false` (kill-switch) + per-tenant `linkedin_enabled`; Telegram/LinkedIn требуют consent/connection.
- **Внешние ключи (dev):** DeepSeek и Langfuse заданы; Serper/Yandex/DaData/Hunter — пустые (sourcing работает
  только через `website_parser`).
- **Тесты:** unit — без внешних зависимостей; integration (`-m integration`) требуют запущенного стека и делают
  реальные LLM-вызовы (медленно).
