#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SVC="${1:?Usage: rebuild.sh <service>}"
COMPOSE="docker compose -f infra/docker-compose.dev.yml --env-file .env"
$COMPOSE build "$SVC"
$COMPOSE up -d --no-deps "$SVC"
$COMPOSE logs --tail=30 "$SVC"
