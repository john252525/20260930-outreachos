#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

set -a; source .env; set +a

FAILED=0
check() {
  local name="$1" url="$2"
  if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
    echo "OK   ${name}"
  else
    echo "FAIL ${name} (${url})"; FAILED=1
  fi
}
check "tenant-service" "http://127.0.0.1:${TENANT_SERVICE_PORT}/healthz"
check "llm-gateway"    "http://127.0.0.1:${LLM_GATEWAY_PORT}/healthz"
check "brief-service"  "http://127.0.0.1:${BRIEF_SERVICE_PORT}/healthz"
check "contact-store"  "http://127.0.0.1:${CONTACT_STORE_PORT}/healthz"
check "dev-console"    "http://127.0.0.1:${DEV_CONSOLE_PORT}/healthz"
check "icp-service"    "http://127.0.0.1:${ICP_SERVICE_PORT}/healthz"
check "sourcing-service" "http://127.0.0.1:${SOURCING_SERVICE_PORT}/healthz"
check "composer-service" "http://127.0.0.1:${COMPOSER_SERVICE_PORT}/healthz"
check "review-queue"    "http://127.0.0.1:${REVIEW_QUEUE_PORT}/healthz"
check "sender-email"    "http://127.0.0.1:${SENDER_EMAIL_PORT}/healthz"
check "reply-classifier" "http://127.0.0.1:${REPLY_CLASSIFIER_PORT}/healthz"
check "analytics-service" "http://127.0.0.1:${ANALYTICS_SERVICE_PORT}/healthz"
check "experiments-service" "http://127.0.0.1:${EXPERIMENTS_SERVICE_PORT}/healthz"
check "orchestrator" "http://127.0.0.1:${ORCHESTRATOR_PORT}/healthz"
check "auto-revision" "http://127.0.0.1:${REVISION_SERVICE_PORT}/healthz"
check "telegram-sender" "http://127.0.0.1:${TELEGRAM_SENDER_PORT}/healthz"
check "linkedin-sender" "http://127.0.0.1:${LINKEDIN_SENDER_PORT}/healthz"
check "users-service" "http://127.0.0.1:${USERS_SERVICE_PORT}/healthz"
check "campaign-service" "http://127.0.0.1:${CAMPAIGN_SERVICE_PORT}/healthz"
check "whatsapp-sender" "http://127.0.0.1:${WHATSAPP_SENDER_PORT}/healthz"
check "realtime-gateway" "http://127.0.0.1:${REALTIME_GATEWAY_PORT}/healthz"
check "ml-scoring-service" "http://127.0.0.1:${ML_SCORING_PORT}/healthz"
check "nats-monitor"   "http://127.0.0.1:${NATS_MONITOR_PORT}/healthz"
[[ $FAILED -eq 0 ]] || exit 1
