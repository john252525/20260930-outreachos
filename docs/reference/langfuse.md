# reference/langfuse.md — Langfuse: интеграция и проверка

> Как мы трейсим LLM-вызовы и как проверить, что они дошли.

## Что делает

Langfuse (cloud) принимает **трейсы** LLM-вызовов: промпт, ответ, модель, токены, стоимость, латентность.
Дашборды и поиск по трейсам — в веб-UI: https://cloud.langfuse.com

## Важно: Langfuse НЕ считает стоимость сам

Мы считаем `cost_usd` у себя (`llm_gateway.pricing`, см. `docs/reference/pricing.md`) и **передаём готовое значение** в Langfuse через `cost_details`.
Так числа в нашей БД (`llm_calls`) и в Langfuse всегда совпадают.

## Где в коде

- `services/llm-gateway/src/llm_gateway/langfuse_client.py` — обёртка SDK v4 (OpenTelemetry-модель).
- `services/llm-gateway/src/llm_gateway/service.py` — вызов `trace_generation` после успешного LLM-ответа.
- `services/llm-gateway/src/llm_gateway/main.py` — инициализация + `flush()` при shutdown.

## Конфиг (.env)

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```
Если ключи пустые — клиент в режиме no-op (трейсы не шлются, ошибок нет).

## SDK: особенности версий

- Используется **langfuse>=3.0** (на момент написания поставилась 4.x).
- API v4 построен на OpenTelemetry. Нет старого `client.trace()`/`trace.generation()`.
- Используем: `client.start_observation(name=..., as_type='generation', model=..., usage_details=..., cost_details=...)` → `obs.end()` → `client.flush()`.

## Проверка, что трейсы дошли (актуально с 2026-09)

ВАЖНО: старый эндпоинт `GET /api/public/traces` для новых организаций возвращает **410 Gone**.
Новый эндпоинт: `GET /api/public/v2/observations` (обязательны `fromStartTime` и `toStartTime`).
По умолчанию список НЕ отдаёт model/usage — нужно указать `fields`.

```bash
PK=$(grep LANGFUSE_PUBLIC_KEY .env | cut -d= -f2)
SK=$(grep LANGFUSE_SECRET_KEY .env | cut -d= -f2)
FROM=$(date -u -d "-1 hour" +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u -d "+1 hour" +%Y-%m-%dT%H:%M:%SZ)
curl -s -u "$PK:$SK" "https://cloud.langfuse.com/api/public/v2/observations?fromStartTime=$FROM&toStartTime=$TO&limit=20&fields=core,model,usage"
```

Ожидаемый ответ: список observations с `model`, `usageDetails` (input/output/total), `costDetails`.

## Проверка, что клиент включён (в сервисе)

В логах `llm-gateway` при старте: `"langfuse_enabled": true`.
Если false — ключи не подхватились (проверить `.env`).
