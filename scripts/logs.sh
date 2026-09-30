#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SVC="${1:?Usage: logs.sh <service>}"
docker compose -f infra/docker-compose.dev.yml --env-file .env logs -f --tail=100 "$SVC"
