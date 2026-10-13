# Iteration 009 — Приведение памяти в порядок (pre-context-reset)

Date: 2026-10-11
Коммит: 1130772

## Goal

Перед переездом в новое окно контекста — провести аудит AGENTS.md/памяти, устранить устаревшее,
чтобы новый агент стартовал «влёт» (с нуля понимал проект, статус, как поднять и проверить).

## Changes

- `AGENTS.md` — переписан: TL;DR (статус, стек, команды, ограничения сервера), порядок чтения,
  чеклист конца итерации (+git push), шаблон файла итерации.
- `docs/memory/STATE.md` — переписан: TL;DR для нового агента, актуальные Done (спринты 0..3),
  Next (Спринт 4/5), карта портов, команды, полезные факты.
- `docs/memory/PROJECT.md` — обновлён: полный пайплайн (сервис → сервис), актуальный состав сервисов,
  интеграции со статусом ключей.
- `docs/memory/DECISIONS.md` — добавлены ADR-013..016 (pipeline из 3 сервисов; dry-run + per-employee
  sender; dev-console как инспектор + admin-DSN; unwrap payload contact-store).
- `docs/memory/CONVENTIONS.md` — добавлены межсервисные паттерны (клиенты, unwrap, flush+refresh,
  NATS-обработчик как Pydantic, LLM JSON retry, фоновые задачи, идемпотентность).
- `docs/memory/GLOSSARY.md` — добавлены термины Спринта 2C/3 (connector, RawCandidate, SearchJob,
  Template, Personalizer, FactChecker, ReviewItem, ramp-up, dry-run, List-Unsubscribe).
- `docs/memory/BACKLOG.md` — переписан: убраны дубли разделов, актуализированы ограничения dev.
- `README.md` — обновлён статус, ссылки на документацию, команды.

## Notes

- Проверки после правок: ruff ✅, mypy ✅ (231 файл), pytest ✅ (104 unit).
- Код не менялся — только документация памяти.
