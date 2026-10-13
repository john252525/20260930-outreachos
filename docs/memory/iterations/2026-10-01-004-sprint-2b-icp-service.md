# Iteration 004 — Спринт 2B: icp-service

Date: 2026-10-01
Коммит: 473357b

## Goal

Превратить Brief в ICP с сегментами через LLM. Изолированный сервис: только brief-service + llm-gateway.

## Changes

- `services/icp-service/` — моделB, weight_normalizer, brief_client, llm (client/schemas/prompts), repository, service, api.
- Таблица `icps` + RLS/FORCE, version, is_active.
- `infra/docker-compose.dev.yml`: icp-service (порт 48104), dev-console +ICP.
- `scripts/migrate.sh`, `scripts/healthcheck.sh`, CI: icp-service.
- `docs/tasks/sprint-2b/`: 6 задач + overview.
- dev-console: вкладка ICP, icp-service в health-грид.

## Key fixes

- `normalize_weights`: компенсация округления нужна и в zero-case (6 x round(1/6) = 1.000002).
- `MissingGreenlet` при revise: flush экспайрит updated_at -> _flush helper с refresh.
- LLM иногда возвращает обрезанный JSON для больших ICP -> LLMGatewayError теперь AppError (502, не 500) + retry до 3 попыток + max_tokens 16384.

## Tests

- unit: weight_normalizer (7), brief_client (2, respx).
- integration: generate/revise/activate/rls (реальный LLM).
- E2E снаружи: 13/13.
- ruff, mypy strict, pytest — зелёные.

## Notes / next

- См. STATE.md. Далее — Спринт 2C (sourcing-service).
