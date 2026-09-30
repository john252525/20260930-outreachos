# Outreach OS — Runbook

## Первый запуск

    cd /opt/20260930-outreachos
    cp .env.example .env    # заполнить секреты
    bash scripts/bootstrap.sh

## Ежедневные операции

    bash scripts/logs.sh tenant-service     # логи сервиса
    bash scripts/rebuild.sh llm-gateway     # пересборка одного сервиса
    bash scripts/migrate.sh                 # применить миграции
    bash scripts/healthcheck.sh             # проверить все сервисы
    bash scripts/psql.sh                    # psql в Postgres
    bash scripts/redis-cli.sh               # redis-cli
    bash scripts/nats-cli.sh stream ls      # NATS CLI

## Типовые проблемы

**Сервис не поднимается** — смотреть `bash scripts/logs.sh <service>`, искать `Traceback`.

**NATS не принимает** — `curl http://127.0.0.1:$NATS_MONITOR_PORT/varz`, проверить `bash scripts/nats-cli.sh stream ls`.

**RLS не работает** — сервис должен ходить под ролью `outreach_app` (NOSUPERUSER, NOBYPASSRLS), у таблиц должен быть `FORCE ROW LEVEL SECURITY`:

    SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='tenants';

**Кэш LLM залип** — `bash scripts/redis-cli.sh --scan --pattern 'llm:cache:*'`, затем `DEL`.

**Полный сброс (dev, УДАЛЯЕТ ДАННЫЕ)** — `bash scripts/bootstrap.sh --reset`.

## NATS JetStream: лимиты хранилища

**Важно:** JetStream бронирует место по сумме `max_bytes` стримов, а не по факту данных. Если сумма броней превысит общий пул (`max_file_store`) — новые стримы не создаются (`insufficient storage resources available`), даже если данных почти нет.

Проверить:

    curl -s http://127.0.0.1:$NATS_MONITOR_PORT/jsz | python3 -c "import sys,json;d=json.load(sys.stdin);print('max_storage:', d['config']['max_storage'], 'reserved:', d['reserved_storage'])"

- `max_storage` — общий пул (сейчас 8 GiB, задан в `infra/nats/nats-server.conf`).
- `reserved_storage` — сумма броней стримов (сейчас ~1.6 GiB), должно быть < `max_storage`.

Фактические данные: `bash scripts/nats-cli.sh stream report`. Потолки стримов — в `libs/nats-client/src/nats_client/streams.py`. Флагов `--js-max-file-store` у nats-server НЕТ — только конфиг-файл (см. ADR-012).

## Бэкап (stage/prod)

    docker exec -T outreach-os-postgres pg_dump -U outreach -Fc outreach > backup-$(date +%F).dump

## Переменные окружения

См. `.env.example`. Ключевые: `POSTGRES_*`, `POSTGRES_APP_*`, `NATS_*`, `REDIS_*`, `DEEPSEEK_API_KEY`, `LANGFUSE_*`, `DEFAULT_PROVIDER` (`mock` для проверки без реальных токенов), порты сервисов.
