# Agent instructions — Outreach OS

Ты работаешь в монорепе **Outreach OS** (мульти-тенантная API-first платформа для outreach).
Этот файл — bootloader. Читай его первым делом при старте сессии.

## Быстрый старт (TL;DR)

- **Статус:** Спринты 0–7 закрыты (0–6 + 7A-F: users+roles+audit, campaign, WhatsApp, realtime, bandit, ML). Web UI + 4 канала (email/Telegram/LinkedIn/WhatsApp). Следующий — **Спринт 8** (multi-region, SSO, billing).
  Актуальное состояние — в `docs/memory/STATE.md`.
- **Стек:** Python 3.12 / FastAPI / Postgres+RLS / NATS JetStream / Redis / uv workspaces / Docker Compose.
- **uv** лежит локально: `export PATH="$PWD/.tools:$PATH"`.
- **Поднять/проверить:** `bash scripts/bootstrap.sh`, `bash scripts/healthcheck.sh`, `bash scripts/migrate.sh`.
- **Проверки:** `uv run ruff check .` · `uv run mypy libs services` · `uv run pytest -q`.
- **Инспектор:** dev-console на `http://<host>:48110/` (сервисы, события NATS, данные).
- **Сервер общий** с чужими проектами — работай только в `/opt/20260930-outreachos`, порты свободные/рандомные,
  чужие контейнеры НЕ трогай. Память/диск «впритык» → при таймауте сборки: `docker builder prune -f`.

## Порядок чтения при старте

1. `docs/memory/PROJECT.md` — что за проект, пайплайн, стек, интеграции
2. `docs/memory/STATE.md` — где мы сейчас (Done / In progress / Next / Blockers) + карта портов
3. `docs/memory/CONVENTIONS.md` — как писать код (в т.ч. межсервисные паттерны)
4. `docs/memory/DECISIONS.md` — принятые архитектурные решения (ADR-001..026; не предлагай отвергнутое)
5. последние 2–3 файла из `docs/memory/iterations/`
6. при необходимости — `docs/memory/GLOSSARY.md`, `docs/memory/BACKLOG.md`

Справочники (когда трогаешь соответствующую область):
- `docs/reference/pricing.md` — цены LLM и как считается стоимость вызова
- `docs/reference/scoring.md` — веса и алгоритм completeness-скоринга брифа
- `docs/reference/langfuse.md` — LLM-трейсинг: как проверить вызовы

## Принципы работы

- **Один источник правды.** «Где мы сейчас» — только в `STATE.md`. Не дублируй это в других файлах.
- **Не ломай чужие сервисы.** Работай только в `/opt/20260930-outreachos`. Деплой — на рандомные/свободные порты.
- **Evidence-принцип.** Любой факт в коде/данных должен иметь источник или быть помечен как гипотеза.
- **Никаких `print`, `time.sleep`, `datetime.utcnow`.** Только structlog, asyncio.sleep, timezone-aware UTC.
- **UUID v7** (`common.uuid7` / `db.types.generate_uuid7`), timestamps — UTC с `Z`.

## End of iteration checklist

1. Все проверки зелёные: `uv run ruff check .`, `uv run mypy libs services`, `uv run pytest -q`
2. Обнови `docs/memory/STATE.md` (Done / In progress / Next / Blockers)
3. Создай `docs/memory/iterations/YYYY-MM-DD-NNN-<slug>.md` (шаблон ниже)
4. Если было архитектурное решение — добавь ADR в `docs/memory/DECISIONS.md`
5. Если появился TODO/долг — добавь в `docs/memory/BACKLOG.md`
6. `git add -A && git commit -m "iter NNN: <summary>"`
7. `git push` (origin — `git@github.com:john252525/20260930-outreachos.git`)

## Шаблон файла итерации

    # Iteration NNN — <короткое название>
    Дата: YYYY-MM-DD
    Коммит: <sha>
    ## Цель
    ## Изменения
    ## Исправления (баги)
    ## Тесты
    ## Заметки / дальше
