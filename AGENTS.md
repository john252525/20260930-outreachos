# Agent instructions — Outreach OS

Ты работаешь в монорепе **Outreach OS** (мульти-тенантная API-first платформа для outreach).
Этот файл — bootloader. Читай его первым делом при старте сессии.

## Порядок чтения при старте

1. `docs/memory/PROJECT.md` — что за проект, архитектура, стек, интеграции
2. `docs/memory/STATE.md` — где мы сейчас (Done / In progress / Next / Blockers)
3. `docs/memory/CONVENTIONS.md` — как писать код в этом репо
4. `docs/memory/DECISIONS.md` — принятые архитектурные решения (не предлагай отвергнутое)
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
