#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a; source .env; set +a
docker exec -it outreach-os-redis redis-cli -a "${REDIS_PASSWORD}" "$@"
