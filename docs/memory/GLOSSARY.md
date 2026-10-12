# GLOSSARY.md — доменные термины

> Чтобы агент не путался в терминах.

## Основные сущности

- **Tenant** (тенант / проект) — изолированное пространство данных. В продукте это «проект» под конкретную нишу (например, «Гидроборты — дистрибьюторы РФ»). Одна БД, изоляция через `tenant_id` + RLS.
- **Brief** — структурированное описание проекта (что продаём, кому, чем отличаемся, цели outreach). Строится из сырых вводных через LLM. Контракт: `libs/contracts/src/contracts/brief.py`.
- **ICP** (Ideal Customer Profile) — профиль идеального клиента/партнёра: отрасли, размер, гео, боли, триггеры, роли ЛПР. Строится из Brief (Спринт 2).
- **Segment** — сегмент внутри ICP (напр. «дистрибьюторы гидробортов в РФ»).
- **Company** — карточка компании-кандидата.
- **Contact** — карточка человека-кандидата (ЛПР/инфлюенсер).
- **Message** — конкретное сообщение конкретному контакту в конкретном канале.
- **Reply** — входящий ответ на Message.
- **Experiment** — A/B-гипотеза по outreach (варианты, метрики, победитель).

## Процессные термины

- **Intake** — приём вводных по проекту (текст/ссылка/транскрипт/ответы). Адаптивный: LLM дозадаёт вопросы.
- **Completeness score** — числовая оценка (0.0–1.0) полноты Brief. Считается детерминированно по весам.
- **Missing info** — список незаполненных полей Brief с приоритетом и объяснением, зачем нужно.
- **Порог (threshold)** — `BRIEF_COMPLETENESS_THRESHOLD`: при `score >= threshold` бриф становится `complete`.
- **Sourcing / OSINT** — поиск конкретных компаний и контактов по ICP (Спринт 2).
- **Evidence** — источник факта (URL + тип источника + сниппет). Evidence-принцип: факт без источника — гипотеза.
- **Ramp-up** — постепенное наращивание объёма отправки (прогрев доменов/ящиков).
- **Human-in-the-loop** — обязательная проверка человеком перед отправкой (review-queue).

## Технические термины

- **RLS** (Row-Level Security) — построчная изоляция в Postgres по `tenant_id`. См. ADR-003.
- **Idempotency-Key** — заголовок, защищающий POST от дублей. Реплей → `X-Idempotent-Replay: true`.
- **Event envelope** — обёртка NATS-события (`event_id`, `event_type`, `schema_version`, `tenant_id`, `trace_id`, `payload`).
- **Stream (NATS)** — контейнер сообщений по subject'ам с retention (`TENANTS`, `BRIEFS`, `LLM_CALLS`, `SYSTEM`).
- **Subject** — иерархический адрес события: `<domain>.<action>.<tenant_id>` (напр. `brief.created.<uuid>`).
- **task_type** — тип LLM-задачи с версией промпта (`brief_extract_v1`). Для A/B и аналитики.
- **Pricing layer** — единый слой расчёта стоимости LLM (цены в конфиге). См. `docs/reference/pricing.md`.
- **Tenant-скоупный** — принадлежащий одному тенанту; обязан содержать `tenant_id`.

## Статусы Brief

- `draft` — создан, но не обработан (начальный).
- `in_progress` — обрабатывается, есть неотвеченные вопросы.
- `complete` — достигнут порог полноты или форсированное завершение.
- `abandoned` — отказ (с причиной в `metadata`).
- `archived` — soft-delete.

## Термины Спринта 2C/3 (sourcing, composer, review, sender)

- **Connector** (коннектор) — абстракция источника в sourcing: `search(criteria) -> RawCandidate[]`. Коннектор только достаёт данные, не нормализует, не скорит, не пишет в БД.
- **RawCandidate** — сырой результат коннектора (URL, title, snippet, domain, raw_payload). Дедуп между коннекторами по `dedup_key()` (домен → URL → title).
- **SearchJob** — единица работы sourcing (таблица `search_jobs`): статус, прогресс, счётчики, стоимость. `SearchJobItem` — по одному кандидату.
- **Normalizer** (sourcing) — LLM-превращение RawCandidate в структурированную Company/Contacts с evidence.
- **Scorer** (sourcing) — детерминированная оценка соответствия ICP по `scoring_weights` сегмента (industry/size/geo/pain/trigger/role). Порог `SOURCING_MIN_SCORE`.
- **Template** (composer) — Python-модуль, рендерящий промпт под канал (`email_cold_outreach_v1`, `email_followup_v1`). Версионируется (`template_id:version`).
- **Personalizer** (composer) — LLM-генерация `{subject, body}` из `RenderedTemplate`.
- **FactChecker** (composer) — детерминированная проверка фактических утверждений в письме (имена/компания/числа). Числа без источника → `is_hypothesis: true` (+ warning).
- **factual_claims** — список утверждений письма с `evidence_url`/`confidence`/`is_hypothesis` (в `message.personalization`).
- **ReviewItem** — запись очереди ревью (таблица `review_items`): `pending | approved | rejected | edited_and_approved | skipped`. `priority` = `high`, если есть warnings/hypotheses.
- **Ramp-up / warm-up** — постепенный рост лимитов отправки нового ящика по дням (Redis-счётчики hourly/daily).
- **SenderAccount / SendAttempt** — подключённый ящик (SMTP/IMAP, пароль зашифрован) и история попыток отправки.
- **Dry-run** — режим sender: письмо не уходит, но попытка и событие логируются (`provider_message_id=dry-run-<id>`).
- **List-Unsubscribe** — заголовок письма для отписки в один клик (требование Gmail/Yandex).

## Спринт 4

- **Composite classifier** — сначала правила, затем LLM (fallback), при ошибке LLM — результат правил или UNKNOWN.
- **ReplyCategory / Sentiment / NextAction** — категория ответа, тональность, рекомендованное действие.
- **needs_review** — статус Reply при confidence < `REPLY_MIN_CONFIDENCE`.
- **Materialized view (MV)** — предпосчитанный агрегат в схеме `analytics`; рефреш по таймеру.
- **Funnel** — contacts → contacted → sent → replied → replied_positive (+ bounced/closed).
- **VariantAssigner** — детерминированное распределение контакта по варианту (sha256 `exp:contact`).
- **StatsEngine** — two-proportion z-test + Wilson CI + Bonferroni-коррекция + MDE.
- **MDE (minimum detectable effect)** — минимальный относительный лифт, который считаем значимым.
- **analytics.alert** — событие при низком reply rate / высоком bounce rate.

## Спринт 5

- **Flow / FlowStep** — цепочка автоматизации и её шаг (orchestrator).
- **EventRouter** — диспатчер NATS-событий по handler'ам.
- **Handler** — обработчик события (создаёт FlowStep, вызывает сервисы).
- **RetryWorker** — переигрывает `retry_scheduled` шаги (backoff, reconciliation, parse_event).
- **Revision** — предложение переписать шаблон (auto-revision); human approve обязателен.
- **TemplateOverride** — data-driven промпт в composer, применяется вместо кодового шаблона.
- **Warm-up (Telegram)** — постепенный рост лимитов (3→30/день).
- **FloodWait** — лимит Telegram; аккаунт помечается и приостанавливается.
- **Consent-гейт** — telegram отправляется только при `messenger_opt_in=granted` или prior reply.

## Спринт 6

- **BFF (backend-for-frontend)** — Next.js API-прокси, скрывает сервисы и секреты от браузера.
- **SERVICE_TOKEN** — общий токен для BFF→сервисы (opt-in enforcement).
- **TenantSettings** — per-tenant конфиг (флаги авто, лимиты, каналы, алерты, квоты, брендинг).
- **LinkedIn double opt-in** — глобальный `LINKEDIN_ENABLED` + per-tenant `linkedin_enabled`.
- **Connection check** — LinkedIn-сообщение только при принятом connection request.
- **Captcha → ручное решение** — аккаунт `captcha_required`, `/solve-captcha`.
- **home_region** — регион хранения данных tenant'а (multi-region groundwork).
