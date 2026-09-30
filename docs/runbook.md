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

## Бэкап (stage/prod)

    docker exec -T outreach-os-postgres pg_dump -U outreach -Fc outreach > backup-$(date +%F).dump

## Переменные окружения

См. `.env.example`. Ключевые: `POSTGRES_*`, `POSTGRES_APP_*`, `NATS_*`, `REDIS_*`, `DEEPSEEK_API_KEY`, `LANGFUSE_*`, `DEFAULT_PROVIDER` (`mock` для проверки без реальных токенов), порты сервисов.
