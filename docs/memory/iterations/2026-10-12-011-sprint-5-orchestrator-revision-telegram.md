# Iteration 011 — Спринт 5: orchestrator + auto-revision + telegram

Дата: 2026-10-12
Коммит: (pending)

## Цель
Сделать платформу самоуправляемой (orchestrator), замкнуть обратную связь (auto-revision) и
добавить второй канал (Telegram).

## Изменения
- **orchestrator** (48114): flows/flow_steps (RLS), EventRouter + 8 handlers, RetryWorker
  (backoff + reconciliation + parse_event), API /flows|/stats|trigger-draft|pause/resume/cancel,
  /metrics (Prometheus). Новый стрим FLOWS + subjects flow.*/revision.*.
- **auto-revision** (48115): revisions (RLS), MetricsAnalyzer + LLMAdvisor + TemplateRevisor,
  propose/approve/reject. approve → template_overrides (composer) + эксперимент.
- **composer**: таблица template_overrides (+ миграция 0002, API /templates/overrides,
  применение активного override в draft с {{var}}-подстановкой).
- **telegram-sender** (48116): telegram_accounts/telegram_send_attempts (RLS), Bot+MTProto
  клиенты, Fernet, warm-up, FloodWait, consent-гейт, dry-run.
- **dev-console**: вкладки Флоу/Ревизии/Telegram.
- Router.subscriber: настраиваемый deliver_policy (NEW для orchestrator).

## Исправления (баги)
- Orchestrator: retry помечал шаг running, но при существующем flow выходил рано → добавлена
  reconciliation + продолжение работы; retry worker строил payload как dict → parse_event
  (типизированная модель).
- Retry/evaluate-loop перечисляли тенантов под app-ролью (RLS → 0) → admin-DSN (ADR-017).
- icp-service терял DNS после `docker stop` → пересоздание контейнера.

## Тесты
- unit: orchestrator (router, errors), auto-revision (analyzer, advisor, revisor),
  telegram (crypto, rampup, limiter). Всего 152 unit в репо.
- integration: +11 (orchestrator, auto-revision, telegram). ruff+mypy (374) — зелёные.

## Заметки / дальше
- Telegram — только Bot по умолчанию; MTProto опционально. Dry-run на dev.
- Далее — Спринт 6 (LinkedIn, WhatsApp, bandit, ML-скоринг, UI, prod).
