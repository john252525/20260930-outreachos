#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"
set -a; source .env; set +a
docker run --rm -it --network outreach-os-net natsio/nats-box:0.16.0 \
  nats -s "nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222" "$@"
