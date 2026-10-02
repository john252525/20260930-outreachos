#!/usr/bin/env bash
# Apply Alembic migrations for every service that has them.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE="docker compose -f infra/docker-compose.dev.yml --env-file .env"
SERVICES=("tenant-service" "llm-gateway" "brief-service" "contact-store" "icp-service" "sourcing-service" "composer-service" "review-queue")

for svc in "${SERVICES[@]}"; do
  if [[ -d "services/${svc}/migrations" ]]; then
    echo "[migrate] ${svc}..."
    $COMPOSE run --rm -T "${svc}" alembic -c alembic.ini upgrade head
  fi
done
echo "[migrate] done"
