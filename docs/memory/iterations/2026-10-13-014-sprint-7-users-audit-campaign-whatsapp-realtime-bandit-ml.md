# Iteration 014 — Спринт 7: Users + Audit + Campaign + WhatsApp + Realtime + Bandit + ML

Дата: 2026-10-13
Коммит: (pending)

## Цель
Сделать систему продуктом для команд: users в БД (роли, audit), кампании, 4-й канал (WhatsApp),
realtime-обновления, bandit, ML-скоринг.

## Изменения
- **7A users-service** (48119): users (глобальные) + user_tenants/invitations (RLS) + схема audit.
  Argon2, JWT (tenant_id+role), constant-time auth, brute-force lock, register (tenant+owner),
  login/switch-tenant/me, invite/accept, audit API. `common.audit`. Web UI: users/audit.
- **7B campaign-service** (48120): campaigns (RLS), CRUD + metrics. Web UI /campaigns.
- **7C whatsapp-sender** (48121): accounts/templates/attempts (RLS), провайдер-абстракция (Gupshup+dry-run),
  24ч session window, pre-approved шаблоны, double opt-in + consent. Webhook.
- **7D realtime-gateway** (48122): WS + Redis pub/sub + NATS-мост (BRIEFS+FLOWS) + presence.
- **7E** Thompson Sampling в experiments (`allocation_strategy=fixed|thompson`).
- **7F ml-scoring-service** (48123): contact_features (RLS), baseline-скоринг.
- **UI polish:** /contacts (+компании), markdown-preview в ревью, /campaigns.
- **dev-console:** 21 сервис.

## Исправления (баги)
- users-service: relationship ambiguity (два FK на users) → foreign_keys; RLS-вставка membership → set_tenant_context;
  login cross-tenant членства → admin-DSN; skip-paths для /auth/me.
- whatsapp: частичная генерация файлов (пересозданы), realtime: удаление пустого tenant-bucket.

## Тесты
- unit: users (password/tokens), campaign (service), whatsapp (window/providers), realtime (connections),
  ml (scorer). Всего 179 unit. ruff+mypy (480) зелёные.

## Заметки / дальше
- 7D.2 optimistic locking (version) — follow-up.
- ML обучение (LightGBM) — отложено (baseline сейчас).
- Далее — Спринт 8 (multi-region, SSO, billing).
