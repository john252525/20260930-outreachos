#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker exec -it outreach-os-postgres psql -U "${POSTGRES_USER:-outreach}" -d "${POSTGRES_DB:-outreach}" "$@"
