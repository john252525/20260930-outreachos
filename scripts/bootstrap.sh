#!/usr/bin/env bash
# Bring up the dev environment from scratch.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE="docker compose -f infra/docker-compose.dev.yml --env-file .env"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
die()  { echo -e "${RED}[bootstrap]${NC} $*" >&2; exit 1; }

command -v docker >/dev/null || die "docker is not installed"
docker compose version >/dev/null || die "docker compose plugin is not installed"
[[ -f .env ]] || die ".env not found. Copy .env.example to .env and fill it in"

if [[ "${1:-}" == "--reset" ]]; then
  warn "Resetting all data volumes..."
  $COMPOSE down -v || true
fi

log "Starting infrastructure (postgres, nats, redis)..."
$COMPOSE up -d postgres nats redis

log "Waiting for Postgres..."
until docker exec outreach-os-postgres pg_isready -U "${POSTGRES_USER:-outreach}" >/dev/null 2>&1; do sleep 1; done
log "Waiting for NATS..."
until curl -fsS "http://127.0.0.1:${NATS_MONITOR_PORT:-8222}/healthz" >/dev/null 2>&1; do sleep 1; done

log "Building service images..."
$COMPOSE build tenant-service llm-gateway

log "Applying migrations..."
bash scripts/migrate.sh

log "Starting services..."
$COMPOSE up -d tenant-service llm-gateway
sleep 5

log "Health check..."
bash scripts/healthcheck.sh || true

log "Done. Tenant service: http://127.0.0.1:${TENANT_SERVICE_PORT}/healthz"
