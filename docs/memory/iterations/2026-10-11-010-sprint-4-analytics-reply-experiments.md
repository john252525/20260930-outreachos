# Iteration 010 — Спринт 4: reply-classifier + analytics + experiments

Дата: 2026-10-11
Коммит: e8a0a7a

## Цель
Замыкание обратной связи: классификация ответов, аналитика метрик, A/B-эксперименты.

## Изменения
- **Новый сервис `reply-classifier`** (порт 48111): таблица `replies` (RLS+FORCE,
  unique `(tenant_id, message_id, from_email)`), `CompositeClassifier` (rule → LLM),
  промпт `reply_classify_v1`, API `/replies*`, событие `reply.classified`.
  Автоотписка при unsubscribe; `replied_positive` при позитиве.
- **Новый сервис `analytics-service`** (порт 48112): схема `analytics` + 5 MV,
  owner-DSN (ADR-017), `MVRefresher` (300с), `AlertEngine` (час, min sample) →
  `analytics.alert`, API `/analytics/*`, кэш Redis 60с.
- **Новый сервис `experiments-service`** (порт 48113): таблица `experiments`
  (RLS+FORCE), `VariantAssigner` (sha256-хеш), `StatsEngine` (z-test + Wilson + Bonferroni + MDE),
  API `/experiments/*`, события `experiment.created`/`experiment.variant_won`, авто-evaluate.
- **Интеграции:** composer → assign_variant (variant_id + template_id варианта);
  `segment_id`/`icp_id` в `personalization`; sender `reply.received` расширен
  (`from_email/from_name/subject/body/received_at/...`); contact-store
  `PATCH /contacts/{id}/outreach-history`.
- **Libs:** новый subject `analytics.alert`; `AnalyticsAlertPayload`; `ReplySnapshot` расширен;
  идемпотентное до-обновление subjects стримов в NATSConnection.
- **dev-console:** вкладки Ответы/Эксперименты/Аналитика; рабочий Swagger-прокси `/docs/{service}`.
- **composer json_utils:** `json.loads(strict=False)` — устойчивость к literal control-characters.

## Исправления (баги)
- `analytics` overview/reply-metrics: `Decimal`/`date` не сериализовались в JSON-кэш → кастомный default.
- `analytics` overview: asyncpg не определял тип параметра `template_id` → `bindparam(String)`.
- `reply.classified` был не в BRIEFS-стриме subjects; bootstrap NATS теперь до-обновляет стримы.
- `reply.received` через nats-box требует заголовок `X-Event-Type` (документировано).

## Тесты
- unit: rule_fallback (9), composite (4), llm_classifier (3), assigner (4), stats (6). Всего в репо 130 unit.
- integration: reply-classifier (3), analytics (3), experiments (5) — зелёные на dev-стеке.
- ruff + mypy (294 файла) + pytest — зелёные.

## Заметки / дальше
- SMTP в dry-run; эксперименты на dev данных дают «недостаточно данных» (ожидаемо).
- Далее — Спринт 5 (orchestrator, auto-revision, cost-tracker, Telegram/WhatsApp).
