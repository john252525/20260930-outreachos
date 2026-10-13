# Iteration 012 — Спринт 6: Web UI + LinkedIn + per-tenant settings + multi-region docs

Дата: 2026-10-12
Коммит: 2e3a35a

## Цель
Вывести систему за пределы «технического пользователя»: Web UI, канал LinkedIn, per-tenant settings.

## Изменения
- **Web UI (`apps/web`, Next.js 15, порт 48117):** Auth.js (credentials+JWT), BFF-прокси
  `/api/proxy/<service>/<path>` с SERVICE_TOKEN, middleware-guard. Страницы: login, dashboard,
  reviews(+detail, approve/reject/edit), flows(+detail), analytics, experiments, revisions,
  messages, settings. Tailwind + UI-компоненты.
- **linkedin-sender (48118):** linkedin_accounts/linkedin_send_attempts (RLS), Fernet, residential-proxy,
  warm-up 5→20/день, клиент абстрагирован (dry-run дефолт, `linkedin-api` lazy), captcha→ручное,
  ban→`linkedin.ban_detected`. Двойной opt-in + connection check.
- **Per-tenant settings:** tenant_settings (RLS, авто-создание), API GET/PATCH, кэш Redis,
  интеграция в orchestrator/composer/linkedin. `require_service_token` в libs/common.
- **Multi-region groundwork:** docs/multi-region.md + runbook.
- **dev-console:** вкладка LinkedIn + data-эндпоинты settings/linkedin.
- **Libs:** subject `linkedin.ban_detected` (стрим FLOWS), payload-модель.

## Исправления (баги)
- orchestrator/composer: импорт `get_redis` при добавлении TenantClient.
- linkedin rampup: типы Any для redis-кэша.

## Тесты
- unit: +linkedin (captcha, rampup, encryptor, dry-run). Всего 162 unit.
- integration: +4 (linkedin account flow, RLS, tenant settings).
- ruff + mypy (403) — зелёные.

## Заметки / дальше
- LinkedIn на dev — dry-run; реальный клиент опционален.
- Web: users в env (→ БД в Спринте 7).
- Далее — Спринт 7 (WhatsApp, bandit, ML-скоринг, users+roles, audit).
