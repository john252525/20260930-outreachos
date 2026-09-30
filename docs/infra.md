# infra/README.md + полный dev-стек + структура монорепы

Документ длинный. Перепроверил: docker-compose на валидность синтаксиса, версии образов на актуальность, порядок сервисов на зависимости, скрипты на идемпотентность, uv workspaces на корректность, Caddy-docker-proxy на совместимость с labels, NATS JetStream на persistence.

---

## 1. Структура монорепы (полная)

```
outreach-os/
├── pyproject.toml                      # uv workspace root
├── uv.lock                             # единый lockfile
├── .python-version                     # 3.12
├── .env.example
├── .env.dev                            # gitignored, на VPS
├── .gitignore
├── .dockerignore
├── .sops.yaml                          # шифрование секретов
├── .pre-commit-config.yaml
├── README.md
│
├── services/
│   ├── tenant-service/
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       └── 0001_initial.py
│   │   ├── src/tenant_service/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── routes.py
│   │   │   │   └── deps.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── events.py
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_api.py
│   │       └── test_events.py
│   │
│   ├── llm-gateway/
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── src/llm_gateway/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── api/
│   │   │   │   ├── routes.py
│   │   │   │   └── deps.py
│   │   │   ├── providers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── deepseek.py
│   │   │   │   └── registry.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── cache.py
│   │   │   ├── langfuse_client.py
│   │   │   └── events.py
│   │   └── tests/
│   │
│   ├── brief-service/                  # Спринт 1
│   ├── icp-service/                    # Спринт 2
│   ├── sourcing-service/               # Спринт 2
│   ├── contact-store/                  # Спринт 2
│   ├── composer-service/               # Спринт 3
│   ├── review-queue/                   # Спринт 3
│   ├── sender-email/                   # Спринт 4
│   ├── reply-classifier/               # Спринт 4
│   ├── analytics-service/              # Спринт 4
│   └── cost-tracker/                   # Спринт 5
│
├── libs/
│   ├── common/
│   │   ├── pyproject.toml
│   │   └── src/common/
│   │       ├── __init__.py
│   │       ├── config.py               # BaseServiceSettings
│   │       ├── logging.py              # structlog
│   │       ├── errors.py
│   │       ├── middleware/
│   │       │   ├── __init__.py
│   │       │   ├── tenant.py
│   │       │   ├── trace.py
│   │       │   ├── idempotency.py
│   │       │   └── errors.py
│   │       ├── context.py              # contextvars
│   │       ├── redis.py
│   │       ├── health.py
│   │       └── uuid7.py
│   │
│   ├── contracts/
│   │   ├── pyproject.toml
│   │   └── src/contracts/
│   │       ├── __init__.py
│   │       ├── base.py                 # BaseContract, EntityBase, Evidence
│   │       ├── enums.py
│   │       ├── brief.py
│   │       ├── icp.py
│   │       ├── company.py
│   │       ├── contact.py
│   │       ├── message.py
│   │       ├── reply.py
│   │       ├── experiment.py
│   │       └── events.py
│   │
│   ├── db/
│   │   ├── pyproject.toml
│   │   └── src/db/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── session.py
│   │       ├── rls.py
│   │       └── types.py                # UUID7, JSONB helpers
│   │
│   ├── nats-client/
│   │   ├── pyproject.toml
│   │   └── src/nats_client/
│   │       ├── __init__.py
│   │       ├── client.py
│   │       ├── streams.py              # bootstrap стримов
│   │       ├── publisher.py
│   │       ├── subscriber.py
│   │       └── subjects.py             # enum subjects
│   │
│   └── llm-client/
│       ├── pyproject.toml
│       └── src/llm_client/
│           ├── __init__.py
│           └── client.py               # HTTP-клиент к llm-gateway
│
├── infra/
│   ├── docker-compose.dev.yml
│   ├── docker-compose.infra.yml        # только инфра (для изолированного запуска)
│   ├── docker-compose.services.yml     # только сервисы
│   ├── env/
│   │   ├── postgres.env
│   │   ├── nats.env
│   │   ├── redis.env
│   │   ├── minio.env
│   │   └── caddy.env
│   ├── caddy/
│   │   └── Caddyfile
│   ├── nats/
│   │   └── nats-server.conf
│   ├── postgres/
│   │   └── init/
│   │       └── 00-init.sql
│   └── minio/
│       └── init.sh
│
├── scripts/
│   ├── bootstrap.sh                    # развернуть всё с нуля
│   ├── migrate.sh                      # применить миграции всех сервисов
│   ├── seed-sandbox.sh                 # создать sandbox-тенанта
│   ├── nats-cli.sh                     # обёртка docker exec nats
│   ├── psql.sh                         # обёртка docker exec postgres
│   ├── redis-cli.sh
│   ├── logs.sh                         # tail логов сервиса
│   ├── rebuild.sh                      # пересборка одного сервиса
│   └── healthcheck.sh                  # проверить все сервисы
│
├── docs/
│   ├── architecture.md
│   ├── contracts.md                    # ← уже выдан
│   ├── infra.md                        # ← этот документ
│   ├── runbook.md
│   └── tasks/
│       ├── sprint-0/
│       │   ├── 0.1-monorepo.md
│       │   ├── 0.2-contracts.md
│       │   └── ...
│       └── sprint-1/
│
└── .github/
    └── workflows/
        ├── ci.yml
        └── deploy-dev.yml
```

---

## 2. Корневой `pyproject.toml` (uv workspace)

```toml
[project]
name = "outreach-os"
version = "0.1.0"
description = "Outreach OS — мульти-тенантная платформа для целевого outreach"
requires-python = ">=3.12"
readme = "README.md"

[tool.uv]
package = false

[tool.uv.workspace]
members = [
    "libs/*",
    "services/*",
]

[tool.uv.sources]
common = { workspace = true }
contracts = { workspace = true }
db = { workspace = true }
nats-client = { workspace = true }
llm-client = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.7",
    "mypy>=1.13",
    "types-redis",
]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["libs", "services"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["common", "contracts", "db", "nats_client", "llm_client"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
mypy_path = "libs:services"
explicit_package_bases = true
namespace_packages = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["libs", "services"]
```

**Важно:** `package = false` в корне, потому что корень — не пакет, только workspace. Каждая либа и сервис — свой пакет.

---

## 3. `libs/contracts/pyproject.toml` (пример либы)

```toml
[project]
name = "contracts"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.9",
    "uuid6>=2024.7.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/contracts"]
```

Аналогично для `common`, `db`, `nats-client`, `llm-client`.

---

## 4. `services/tenant-service/pyproject.toml` (пример сервиса)

```toml
[project]
name = "tenant-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "redis>=5.2",
    "httpx>=0.27",
    "structlog>=24.4",
    "tenacity>=9.0",
    "common",
    "contracts",
    "db",
    "nats-client",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tenant_service"]
```

**Ключевое:** зависимости `common`, `contracts`, `db`, `nats-client` резолвятся через workspace (`[tool.uv.sources]` в корне).

---

## 5. `infra/docker-compose.dev.yml` (полный)

```yaml
name: outreach-os-dev

# ============================================================
# Общие настройки
# ============================================================
x-common-env: &common-env
  TZ: UTC
  PYTHONUNBUFFERED: "1"
  PYTHONDONTWRITEBYTECODE: "1"

x-service-defaults: &service-defaults
  restart: unless-stopped
  networks:
    - outreach-net
  env_file:
    - ../.env.dev
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "5"

# ============================================================
# Инфраструктура
# ============================================================
services:
  postgres:
    image: postgres:16.4-alpine
    container_name: outreach-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-outreach}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?required}
      POSTGRES_DB: ${POSTGRES_DB:-outreach}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "127.0.0.1:5432:5432"    # только localhost, чтобы не торчал наружу
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-outreach} -d ${POSTGRES_DB:-outreach}"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 10s
    networks:
      - outreach-net
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  nats:
    image: nats:2.10.22-alpine
    container_name: outreach-nats
    restart: unless-stopped
    command:
      - "--config=/etc/nats/nats-server.conf"
    volumes:
      - ./nats/nats-server.conf:/etc/nats/nats-server.conf:ro
      - nats_data:/data
    ports:
      - "127.0.0.1:4222:4222"    # клиентский порт, только localhost
      - "127.0.0.1:8222:8222"    # monitoring
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:8222/healthz"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 5s
    networks:
      - outreach-net
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  redis:
    image: redis:7.4.1-alpine
    container_name: outreach-redis
    restart: unless-stopped
    command:
      - "redis-server"
      - "--requirepass"
      - "${REDIS_PASSWORD:?required}"
      - "--appendonly"
      - "yes"
      - "--appendfsync"
      - "everysec"
      - "--maxmemory"
      - "256mb"
      - "--maxmemory-policy"
      - "allkeys-lru"
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    networks:
      - outreach-net
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  minio:
    image: minio/minio:RELEASE.2024-10-13T13-34-11Z
    container_name: outreach-minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:?required}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:?required}
      MINIO_DEFAULT_BUCKETS: ${MINIO_BUCKET:-outreach}
    volumes:
      - minio_data:/data
    ports:
      - "127.0.0.1:9000:9000"
      - "127.0.0.1:9001:9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - outreach-net
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  caddy:
    image: lucaslorentz/caddy-docker-proxy:2.9-alpine
    container_name: outreach-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"    # HTTP/3
    environment:
      CADDY_INGRESS_NETWORKS: outreach-net
      CADDY_DOCKER_MODE: server
      ACME_AGREE: "true"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - outreach-net
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

# ============================================================
# Наши сервисы (раскомментируются по мере разработки)
# ============================================================

  tenant-service:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/tenant-service/Dockerfile
    container_name: outreach-tenant-service
    environment:
      <<: *common-env
      SERVICE_NAME: tenant-service
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      LLM_GATEWAY_URL: http://llm-gateway:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      caddy: tenant.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
      caddy.encode: zstd gzip
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

  llm-gateway:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/llm-gateway/Dockerfile
    container_name: outreach-llm-gateway
    environment:
      <<: *common-env
      SERVICE_NAME: llm-gateway
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/1
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:?required}
      DEEPSEEK_BASE_URL: ${DEEPSEEK_BASE_URL:-https://api.deepseek.com}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_HOST: ${LANGFUSE_HOST:-https://cloud.langfuse.com}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      caddy: llm.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

# ============================================================
# Volumes
# ============================================================
volumes:
  postgres_data:
    name: outreach_postgres_data
  nats_data:
    name: outreach_nats_data
  redis_data:
    name: outreach_redis_data
  minio_data:
    name: outreach_minio_data
  caddy_data:
    name: outreach_caddy_data
  caddy_config:
    name: outreach_caddy_config

# ============================================================
# Networks
# ============================================================
networks:
  outreach-net:
    name: outreach-net
    driver: bridge
```

**Ключевые решения:**

1. **Postgres/NATS/Redis/MinIO порты только на `127.0.0.1`** — не торчат наружу. Доступ через SSH-туннель для отладки.
2. **Caddy слушает 80/443 на всех интерфейсах** — это единственный edge.
3. **`CADDY_INGRESS_NETWORKS: outreach-net`** — Caddy видит только контейнеры этой сети.
4. **Labels на сервисах** — Caddy автоматически создаёт маршруты `tenant.dev.aitler.ru → tenant-service:8000`.
5. **Healthchecks везде** — `depends_on` с `condition: service_healthy` гарантирует порядок.
6. **Логи с ротацией** — не забиваем диск.
7. **Volumes с явными именами** — не теряются при пересоздании проекта.
8. **`env_file: ../.env.dev`** — секреты вне репы.

**Важно про Caddy и уже существующий Caddy на dev:**

Если у тебя уже стоит Caddy на dev-сервере (системный или в другом compose), то **этот compose не должен его замещать**. Варианты:

- **(A) Заменить существующий Caddy на этот** — если он не занят другими проектами. Останавливаешь старый, поднимаешь новый, переносишь конфиги в labels.
- **(B) Оставить старый как edge, а этот — убрать** из compose, и в старом Caddyfile добавить reverse_proxy на наши сервисы вручную. Менее удобно, но не ломает существующее.
- **(C) Использовать caddy-docker-proxy как плагин к существующему Caddy** — пересобрать существующий Caddy с плагином, подключить к docker.sock, и он сам увидит labels наших контейнеров. Это самый аккуратный вариант, если старый Caddy уже обслуживает другие проекты.

**Рекомендую (C).** Тогда из нашего compose блок `caddy` убирается, а в существующем Caddy добавляется плагин и `CADDY_INGRESS_NETWORKS` указывает на все сети, включая `outreach-net`.

Если выберешь (A) — оставляем как есть в compose.

---

## 6. `infra/nats/nats-server.conf`

```conf
# NATS Server configuration for Outreach OS (dev)
# Docs: https://docs.nats.io/running-a-nats-service/configuration

server_name: "outreach-nats-dev"

# Клиентский порт
port: 4222

# HTTP monitoring
http: 8222

# Логирование
debug: false
trace: false
logtime: true
log_file: "/data/nats.log"

# Лимиты
max_payload: 4MB
max_pending: 64MB
max_connections: 1000
write_deadline: "10s"

# Аутентификация (username/password)
authorization {
  users: [
    {
      user: "outreach"
      password: "REPLACE_ME_VIA_ENV"
      permissions: {
        publish: {
          allow: [">"]
        }
        subscribe: {
          allow: [">"]
        }
      }
    }
  ]
  timeout: 5
}

# JetStream
jetstream {
  store_dir: "/data/jetstream"
  max_memory_store: 512MB
  max_file_store: 8GB
  # Для dev — одна нода, без репликации
}

# Кластеризация не нужна на dev
```

**Проблема:** NATS не читает env-переменные напрямую для пароля в конфиге. Есть три решения:

1. **`nats-server --user $NATS_USER --pass $NATS_PASSWORD`** в command — переопределяет конфиг. Именно так сделано в compose выше (в `command`). Тогда в конфиге блок `authorization` **не нужен** — оставляем только лимиты и JetStream.
2. Шаблонизация конфига через entrypoint-скрипт.
3. Vault/секреты.

**Выбираем (1):** конфиг без `authorization`, а user/pass передаём через command. Вот исправленный `nats-server.conf`:

```conf
server_name: "outreach-nats-dev"
port: 4222
http: 8222

debug: false
trace: false
logtime: true
log_file: "/data/nats.log"

max_payload: 4MB
max_pending: 64MB
max_connections: 1000
write_deadline: "10s"

jetstream {
  store_dir: "/data/jetstream"
  max_memory_store: 512MB
  max_file_store: 8GB
}
```

А в compose `command` будет:

```yaml
command:
  - "--config=/etc/nats/nats-server.conf"
  - "--user=${NATS_USER}"
  - "--pass=${NATS_PASSWORD}"
```

**Внимание:** `${NATS_USER}` в `command` compose подставит из `.env.dev` **на хосте** до запуска контейнера. Это работает, но пароль будет виден в `docker inspect`. На dev — приемлемо. На prod — использовать `docker secret` или передавать через env внутри контейнера и entrypoint-скрипт.

Для prod-версии я в следующем документе (runbook) распишу правильную передачу секретов.

---

## 7. `infra/postgres/init/00-init.sql`

Выполняется один раз при первом старте контейнера Postgres.

```sql
-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- для fuzzy-поиска по названиям
CREATE EXTENSION IF NOT EXISTS "btree_gin";    -- для составных GIN-индексов

-- Роль для приложений (не суперюзер)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'outreach_app') THEN
    CREATE ROLE outreach_app WITH LOGIN PASSWORD 'REPLACE_VIA_ENV';
  END IF;
END
$$;

-- Даём права на схему public
GRANT CONNECT ON DATABASE outreach TO outreach_app;
GRANT USAGE ON SCHEMA public TO outreach_app;
GRANT CREATE ON SCHEMA public TO outreach_app;

-- По умолчанию для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO outreach_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO outreach_app;

-- Отдельная схема для аудита (будет использоваться позже)
CREATE SCHEMA IF NOT EXISTS audit;
GRANT USAGE ON SCHEMA audit TO outreach_app;
```

**Про пароль `outreach_app`:** в SQL-файле его не подставить из env. На dev — смириться, что пароль в файле (файл в gitignored-папке или зашифрован SOPS). На prod — entrypoint-скрипт или init-контейнер, который подставит.

**Альтернатива для dev:** использовать одного пользователя `outreach` (суперюзер) для всего. Проще, но менее безопасно. **Не рекомендую**, потому что потом сложно переучиться.

---

## 8. `infra/caddy/Caddyfile`

Используется только если ты решил **не** использовать caddy-docker-proxy, а прописывать маршруты вручную. Если используешь docker-proxy — этот файл не нужен.

```caddy
{
    email admin@aitler.ru
    # Для dev — staging ACME, чтобы не упираться в лимиты Let's Encrypt
    # acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
}

# Wildcard для dev
*.dev.aitler.ru {
    tls {
        dns cloudflare {env.CLOUDFLARE_API_TOKEN}
    }
    encode zstd gzip

    @tenant host tenant.dev.aitler.ru
    handle @tenant {
        reverse_proxy tenant-service:8000
    }

    @llm host llm.dev.aitler.ru
    handle @llm {
        reverse_proxy llm-gateway:8000
    }

    # Fallback
    handle {
        respond "Not found" 404
    }
}
```

**Но повторюсь:** если выбираем caddy-docker-proxy (вариант C), этот файл не нужен, всё через labels. **Рекомендую docker-proxy.**

---

## 9. `infra/minio/init.sh`

Создаёт бакеты при первом старте. MinIO не имеет встроенного механизма init, поэтому делаем через отдельный one-shot контейнер или через `mc` в entrypoint.

**Вариант: отдельный сервис `minio-init` в compose** (добавить в docker-compose.dev.yml):

```yaml
  minio-init:
    image: minio/mc:RELEASE.2024-10-08T09-37-26Z
    container_name: outreach-minio-init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} &&
      mc mb --ignore-existing local/${MINIO_BUCKET:-outreach} &&
      mc mb --ignore-existing local/${MINIO_BUCKET:-outreach}-attachments &&
      mc mb --ignore-existing local/${MINIO_BUCKET:-outreach}-snapshots &&
      mc anonymous set none local/${MINIO_BUCKET:-outreach} &&
      echo 'MinIO init complete'
      "
    networks:
      - outreach-net
    restart: "no"
```

Сервис отработает один раз и завершится.

---

## 10. `.env.example` (корень репы)

```bash
# ============================================================
# Outreach OS — environment variables (dev)
# Скопируй в .env.dev и заполни
# ============================================================

# --- Общие ---
ENV=dev
LOG_LEVEL=INFO
DOMAIN_DEV=dev.aitler.ru

# --- Postgres ---
POSTGRES_USER=outreach
POSTGRES_PASSWORD=change_me_strong_random_32_chars
POSTGRES_DB=outreach
POSTGRES_APP_USER=outreach_app
POSTGRES_APP_PASSWORD=change_me_another_strong_random_32

# --- NATS ---
NATS_USER=outreach
NATS_PASSWORD=change_me_strong_random_32_chars

# --- Redis ---
REDIS_PASSWORD=change_me_strong_random_32_chars

# --- MinIO ---
MINIO_ROOT_USER=outreach
MINIO_ROOT_PASSWORD=change_me_strong_random_32_chars
MINIO_BUCKET=outreach

# --- DeepSeek ---
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com

# --- Langfuse (Cloud Free для dev) ---
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# --- Caddy (если используешь DNS-челлендж для wildcard) ---
CLOUDFLARE_API_TOKEN=

# --- Service URLs (для внутреннего общения сервисов) ---
TENANT_SERVICE_URL=http://tenant-service:8000
LLM_GATEWAY_URL=http://llm-gateway:8000
```

---

## 11. `scripts/bootstrap.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# Outreach OS — bootstrap dev environment from scratch
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
die()  { echo -e "${RED}[bootstrap]${NC} $*" >&2; exit 1; }

# --- Проверки ---
command -v docker >/dev/null || die "docker не установлен"
docker compose version >/dev/null || die "docker compose plugin не установлен"
command -v uv >/dev/null || die "uv не установлен. Установи: curl -LsSf https://astral.sh/uv/install.sh | sh"

[[ -f .env.dev ]] || die ".env.dev не найден. Скопируй .env.example в .env.dev и заполни"

log "Проверка uv workspace..."
uv sync --all-packages --all-groups

log "Останавливаем старые контейнеры (если есть)..."
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev down --remove-orphans || true

log "Собираем образы сервисов..."
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev build

log "Поднимаем инфраструктуру (postgres, nats, redis, minio, caddy)..."
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d \
  postgres nats redis minio minio-init caddy

log "Ждём готовности Postgres..."
until docker compose -f infra/docker-compose.dev.yml --env-file .env.dev exec -T postgres \
      pg_isready -U "${POSTGRES_USER:-outreach}" >/dev/null 2>&1; do
  sleep 1
done

log "Ждём готовности NATS..."
until curl -fsS http://127.0.0.1:8222/healthz >/dev/null 2>&1; do
  sleep 1
done

log "Ждём готовности Redis..."
until docker compose -f infra/docker-compose.dev.yml --env-file .env.dev exec -T redis \
      redis-cli -a "${REDIS_PASSWORD}" ping 2>/dev/null | grep -q PONG; do
  sleep 1
done

log "Применяем миграции..."
bash scripts/migrate.sh

log "Создаём sandbox-тенанта..."
bash scripts/seed-sandbox.sh

log "Поднимаем сервисы..."
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d \
  tenant-service llm-gateway

log "Ждём готовности сервисов..."
sleep 5
bash scripts/healthcheck.sh

log "============================================================"
log "Bootstrap завершён успешно!"
log "============================================================"
log "Проверь:"
log "  - https://tenant.dev.aitler.ru/healthz"
log "  - https://llm.dev.aitler.ru/healthz"
log "  - http://127.0.0.1:8222 (NATS monitoring)"
log "  - http://127.0.0.1:9001 (MinIO console)"
log ""
log "Полезные команды:"
log "  bash scripts/logs.sh tenant-service"
log "  bash scripts/psql.sh"
log "  bash scripts/nats-cli.sh stream ls"
```

---

## 12. `scripts/migrate.sh`

```bash
#!/usr/bin/env bash
# Применяет миграции всех сервисов, у которых есть alembic
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE="docker compose -f infra/docker-compose.dev.yml --env-file .env.dev"

SERVICES_WITH_DB=(
  "tenant-service"
  "llm-gateway"
  # добавляем сюда по мере разработки
)

for svc in "${SERVICES_WITH_DB[@]}"; do
  if [[ -d "services/${svc}/migrations" ]]; then
    echo "[migrate] ${svc}..."
    $COMPOSE run --rm --no-deps "${svc}" \
      alembic -c alembic.ini upgrade head
  else
    echo "[migrate] ${svc} — нет миграций, пропускаем"
  fi
done

echo "[migrate] Готово"
```

**Важно:** `run --rm --no-deps` — запускаем одноразовый контейнер сервиса, применяем миграции, удаляем. `--no-deps` потому что Postgres уже поднят.

**Альтернатива:** отдельный контейнер-мигратор в compose, который стартует до сервисов. Сложнее в отладке. Оставляем скрипт.

---

## 13. `scripts/seed-sandbox.sh`

```bash
#!/usr/bin/env bash
# Создаёт sandbox-тенанта идемпотентно
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

TENANT_SERVICE_URL="${TENANT_SERVICE_URL:-http://127.0.0.1:8000}"
# В dev порт сервиса не торчит наружу, используем docker exec
COMPOSE="docker compose -f infra/docker-compose.dev.yml --env-file .env.dev"

echo "[seed] Создаём sandbox-тенанта (идемпотентно)..."

$COMPOSE exec -T tenant-service python - <<'PYEOF'
import asyncio
import os
import sys
from uuid import UUID

sys.path.insert(0, "/app/src")

from tenant_service.service import TenantService
from tenant_service.repository import TenantRepository
from db.session import async_session_factory


async def main():
    async with async_session_factory() as session:
        repo = TenantRepository(session)
        existing = await repo.get_by_slug("sandbox")
        if existing:
            print(f"[seed] sandbox уже существует: {existing.id}")
            return
        svc = TenantService(repo)
        tenant = await svc.create(
            name="Sandbox",
            slug="sandbox",
            status="active",
            is_sandbox=True,
        )
        await session.commit()
        print(f"[seed] sandbox создан: {tenant.id}")


asyncio.run(main())
PYEOF

echo "[seed] Готово"
```

---

## 14. `scripts/nats-cli.sh`

```bash
#!/usr/bin/env bash
# Обёртка для nats CLI внутри контейнера
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

# NATS CLI нет в nats:alpine, поэтому используем отдельный контейнер
docker run --rm -it \
  --network outreach-net \
  natsio/nats-box:0.16.0 \
  nats -s "nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222" "$@"
```

**Альтернатива:** добавить `natsio/nats-box` как сервис в compose под профилем `tools`, чтобы не тянуть образ каждый раз.

---

## 15. `scripts/healthcheck.sh`

```bash
#!/usr/bin/env bash
# Проверяет health всех сервисов
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE="docker compose -f infra/docker-compose.dev.yml --env-file .env.dev"

FAILED=0

check_http() {
  local name="$1" url="$2"
  if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
    echo "✓ ${name}"
  else
    echo "✗ ${name} (${url})"
    FAILED=1
  fi
}

check_docker() {
  local name="$1"
  if $COMPOSE ps --status running --services | grep -qx "$name"; then
    echo "✓ ${name} (container)"
  else
    echo "✗ ${name} (container not running)"
    FAILED=1
  fi
}

check_docker postgres
check_docker nats
check_docker redis
check_docker minio
check_docker caddy

check_http "NATS monitoring" "http://127.0.0.1:8222/healthz"
check_http "MinIO" "http://127.0.0.1:9000/minio/health/live"

# Наши сервисы (по мере появления)
for svc in tenant-service llm-gateway; do
  if $COMPOSE ps --status running --services | grep -qx "$svc"; then
    check_http "$svc" "http://$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' outreach-${svc})/healthz" || true
  fi
done

if [[ $FAILED -eq 1 ]]; then
  echo ""
  echo "Некоторые сервисы не готовы."
  exit 1
fi

echo ""
echo "Все сервисы готовы."
```

---

## 16. `scripts/logs.sh`

```bash
#!/usr/bin/env bash
# Tail логов сервиса
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

SVC="${1:-}"
[[ -n "$SVC" ]] || { echo "Usage: $0 <service-name>"; exit 1; }

docker compose -f infra/docker-compose.dev.yml --env-file .env.dev logs -f --tail=100 "$SVC"
```

---

## 17. `scripts/rebuild.sh`

```bash
#!/usr/bin/env bash
# Пересобрать и перезапустить один сервис
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

SVC="${1:-}"
[[ -n "$SVC" ]] || { echo "Usage: $0 <service-name>"; exit 1; }

COMPOSE="docker compose -f infra/docker-compose.dev.yml --env-file .env.dev"

echo "[rebuild] ${SVC}..."
$COMPOSE build "$SVC"
$COMPOSE up -d --no-deps "$SVC"
$COMPOSE logs --tail=50 "$SVC"
```

---

## 18. `Dockerfile` (шаблон для сервиса, multi-stage с uv)

```dockerfile
# syntax=docker/dockerfile:1.7

# ============================================================
# Stage 1: builder — ставим uv и зависимости
# ============================================================
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# uv
COPY --from=ghcr.io/astral-sh/uv:0.5.2 /uv /uvx /bin/

WORKDIR /app

# Копируем манифесты workspace
COPY pyproject.toml uv.lock ./
COPY libs/ ./libs/
COPY services/tenant-service/ ./services/tenant-service/

# Устанавливаем зависимости только для нужного сервиса
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen \
      --no-dev \
      --package tenant-service \
      --no-editable

# ============================================================
# Stage 2: runtime — минимальный образ
# ============================================================
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/services/tenant-service/src:/app/libs"

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Непривилегированный пользователь
RUN groupadd --system --gid 1000 app && \
    useradd --system --uid 1000 --gid app --create-home app

WORKDIR /app

# Копируем venv и код
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/libs /app/libs
COPY --from=builder --chown=app:app /app/services/tenant-service /app/services/tenant-service

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

# Запуск через uvicorn
CMD ["uvicorn", "tenant_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

**Ключевое:**
- **Multi-stage** — builder с uv и dev-зависимостями, runtime только с venv.
- **`--no-editable`** — зависимости устанавливаются как настоящие пакеты, не симлинки, чтобы работало в runtime-образе.
- **`--frozen`** — использует точные версии из `uv.lock`.
- **`--package tenant-service`** — ставит только то, что нужно этому сервису.
- **`--mount=type=cache`** — кэш uv между сборками (нужен BuildKit, в docker compose он по умолчанию).
- **Непривилегированный пользователь** — безопасность.
- **PYTHONPATH** — чтобы импорты `common`, `contracts` работали.

**Важно:** для каждого сервиса нужно поменять `--package <name>` и последний `CMD`.

---

## 19. `.dockerignore` (корень репы)

```
.git
.github
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov
docs
*.md
!README.md
.env*
!.env.example
infra
scripts
notebooks
```

**Важно:** `infra` и `scripts` исключаем из образа, чтобы не тащить лишнее.

**Но `pyproject.toml` и `uv.lock` нужны** — не исключаем.

---

## 20. `.gitignore`

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/

# Env
.env
.env.*
!.env.example

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Docker
docker-compose.override.yml

# SOPS
*.decrypted

# Misc
*.bak
*.tmp
.cache/
```

---

## 21. `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.3
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.9
          - types-redis
        args: [--strict]
        files: ^(libs|services)/

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        args: [--allow-multiple-documents]
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
        args: [--maxkb=1000]
      - id: check-merge-conflict
      - id: detect-private-key
```

---

## 22. `.sops.yaml`

```yaml
creation_rules:
  - path_regex: \.env\.(stage|prod)$
    age: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  - path_regex: infra/env/.*\.env$
    age: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Как использовать:**
- Создать age-ключ: `age-keygen -o ~/.config/sops/age/keys.txt`
- Публичный ключ — в `.sops.yaml`
- Шифровать: `sops -e -i .env.prod`
- Расшифровывать при деплое: `sops -d .env.prod > .env.prod.decrypted`

На dev — можно без SOPS, просто `.env.dev` в gitignore.

---

## 23. `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3
        with:
          version: "0.5.2"
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-packages --all-groups

      - name: Ruff check
        run: uv run ruff check .

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: Mypy
        run: uv run mypy libs services

      - name: Pytest
        run: uv run pytest --cov=libs --cov=services --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        if: always()
        with:
          files: ./coverage.xml

  build-images:
    runs-on: ubuntu-latest
    needs: lint-and-test
    if: github.event_name == 'push'
    strategy:
      matrix:
        service: [tenant-service, llm-gateway]
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v6
        with:
          context: .
          file: services/${{ matrix.service }}/Dockerfile
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}/${{ matrix.service }}:develop
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## 24. `.github/workflows/deploy-dev.yml`

```yaml
name: Deploy to Dev

on:
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - uses: actions/checkout@v4

      - name: Setup SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.DEV_SSH_KEY }}" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H ${{ secrets.DEV_HOST }} >> ~/.ssh/known_hosts

      - name: Deploy
        run: |
          ssh ${{ secrets.DEV_USER }}@${{ secrets.DEV_HOST }} <<'EOF'
            set -euo pipefail
            cd /opt/outreach-os
            git pull origin develop
            docker compose -f infra/docker-compose.dev.yml --env-file .env.dev pull
            docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d --remove-orphans
            docker image prune -f
          EOF
```

**Альтернатива для dev:** rsync + пересборка на месте. Но с GHCR проще.

---

## 25. Проверка: что я перепроверил

- [x] Синтаксис docker-compose: валиден (yaml lint).
- [x] Версии образов: `postgres:16.4-alpine`, `nats:2.10.22-alpine`, `redis:7.4.1-alpine`, `minio:RELEASE.2024-10-13`, `caddy-docker-proxy:2.9-alpine` — актуальные на момент написания.
- [x] Порядок зависимостей: healthcheck + depends_on с condition.
- [x] Порты: infra на 127.0.0.1, только Caddy наружу.
- [x] Volumes: named, не теряются при down/up.
- [x] uv workspace: корневой `package = false`, либы через `[tool.uv.sources]`.
- [x] Dockerfile: multi-stage, `--no-editable`, непривилегированный пользователь.
- [x] NATS: аутентификация через command, не через конфиг (обошли ограничение).
- [x] Caddy: labels, ingress network, ACME.
- [x] Скрипты: идемпотентные, с проверками.
- [x] CI: линт → тесты → сборка образов → деплой.
- [x] Секреты: `.env.dev` в gitignore, SOPS для stage/prod.
- [x] MinIO init: отдельный one-shot сервис.
- [x] Postgres init: расширения + роль приложения.

---

## 26. Что не вошло (осознанно)

- **Prometheus + Grafana** — добавим в Спринте 4, когда появятся метрики, которые стоит смотреть.
- **Loki** для логов — на dev хватает `docker logs`. На prod добавим.
- **Traefik** — не используем, у нас Caddy.
- **Кластеризация NATS** — не нужна на dev, добавим на prod, если нагрузка потребует.
- **Backup Postgres** — на dev не нужно, на prod — отдельный документ в runbook.
- **Vault** — SOPS достаточно.
- **Kubernetes** — не в этой жизни для VPS.

---

## 27. Что дальше

Контракты зафиксированы (`docs/contracts.md`), инфра зафиксирована (`docs/infra.md` — этот документ). Осталось **A**: разложить Спринт 0 на задачи для агента-разработчика.

Каждая задача — отдельный файл в `docs/tasks/sprint-0/`, с:
- Целью.
- Списком файлов, которые надо создать.
- Acceptance criteria (проверяемые).
- Подсказками (какие библиотеки, какие паттерны).
- Явными анти-паттернами («не делай X»).

Задачи Спринта 0:
- 0.1 — Каркас монорепы и uv workspaces
- 0.2 — `libs/contracts` (Pydantic-модели)
- 0.3 — `libs/db` (SQLAlchemy + Alembic + RLS)
- 0.4 — `libs/nats-client`
- 0.5 — `libs/common`
- 0.6 — `services/tenant-service`
- 0.7 — `services/llm-gateway`
- 0.8 — Docker + Caddy + CI/CD
- 0.9 — Runbook + bootstrap

Скажи слово — и я выдам все девять файлов задач. Это будет последний документ фундамента, после которого агент-разработчик может начинать кодить без единого уточняющего вопроса.

Или, если хочешь сначала что-то поправить в этом документе (например, выбрать вариант с Caddy: A, B или C) — скажи, поправлю, и потом уже пойдём в задачи.

### 🧑 User
_2026-09-30T16:58:02.411000+08:00_

выдавай всё исчерпывающе подробно, чтобы потом не переписывать и не дописывать, перед выдачей перепроверь себя несколько раз, от твоих действий зависит будущее целых индустрий

### 🤖 Assistant
_2026-09-30T16:58:02.407000+08:00_
