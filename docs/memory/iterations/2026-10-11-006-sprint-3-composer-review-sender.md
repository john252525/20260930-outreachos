# Iteration 006-008 — Спринт 3: composer + review-queue + sender-email

Date: 2026-10-11
Коммит: c0d7dda

## Goal

Полный outreach-цикл: генерация письма → ревью человеком → отправка (dry-run).

## Changes

- `services/composer-service`: templates (registry, cold/followup), personalizer, fact-checker, messages table, events.
- `services/review-queue`: review_items, NATS-подписка на message.drafted, approve/reject/edit/assign/bulk.
- `services/sender-email`: sender_accounts + send_attempts, SMTP-клиент, шифрование паролей (Fernet), ramp-up,
  AccountSelector, stop-list, NATS-подписка на message.approved, dry-run.
- compose/migrate/healthcheck/CI: +3 сервиса (порты 48106/48107/48108).
- dev-console: вкладки Письма, Ревью; сервисы composer/review-queue.

## Key fixes

- review-queue: `envelope.payload` — Pydantic-модель, не dict → `.message.id`.
- composer: `_unwrap` для contact-store (поля в `payload`), иначе recipient_snapshot пустой.
- composer PATCH: добавлены `delivery`/`engagement`/`sent_at` (sender шлёт delivery → 422).
- sender: `data.get(k, default)` возвращал None при явном null → `data.get(k) or default`.
- fact-checker: дедуп unverified_number.
- VPS: память/диск впритык → `docker builder prune`.

## Tests

- unit: composer (10), sender (4). E2E Спринта 3: draft→review→approve→dry-run send.
- integration: composer, review-queue, sender (полный цикл).
- ruff, mypy strict, pytest — зелёные.

## Notes / next

- SMTP в dry-run (нет реальных ящиков). Ramp-up проверен (daily=5 на день 1).
- Далее — Спринт 4 (analytics + reply-classifier + A/B).
