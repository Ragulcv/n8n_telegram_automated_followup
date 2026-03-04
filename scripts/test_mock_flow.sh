#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "[FAIL] .env missing. Run ./scripts/prepare_beginner_env.sh first"
  exit 1
fi

get_env() {
  local key="$1"
  grep -E "^${key}=" .env | head -n1 | cut -d'=' -f2-
}

BRIDGE_PORT="$(get_env BRIDGE_PORT)"
N8N_PORT="$(get_env N8N_PORT)"
BRIDGE_API_KEY="$(get_env BRIDGE_API_KEY)"
TELEGRAM_MOCK_MODE="$(get_env TELEGRAM_MOCK_MODE)"

if [[ "${TELEGRAM_MOCK_MODE:-true}" != "true" ]]; then
  echo "[FAIL] TELEGRAM_MOCK_MODE is not true. Set TELEGRAM_MOCK_MODE=true for safe test run."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[FAIL] Docker daemon is not running"
  exit 1
fi

echo "[1/5] Starting containers..."
docker compose up -d --build

echo "[2/5] Waiting for bridge health..."
for _ in {1..30}; do
  if curl -fsS "http://localhost:${BRIDGE_PORT:-8080}/health" >/dev/null 2>&1; then
    echo "[PASS] Bridge is healthy"
    break
  fi
  sleep 2
done

if ! curl -fsS "http://localhost:${BRIDGE_PORT:-8080}/health" >/dev/null 2>&1; then
  echo "[FAIL] Bridge did not become healthy"
  exit 1
fi

echo "[3/5] Checking authenticated account health..."
ACCOUNT_JSON="$(curl -fsS -H "x-api-key: ${BRIDGE_API_KEY}" "http://localhost:${BRIDGE_PORT:-8080}/v1/account/health")"
echo "$ACCOUNT_JSON"

echo "[4/5] Sending mock outbound message through bridge..."
SEND_JSON="$(curl -fsS -X POST "http://localhost:${BRIDGE_PORT:-8080}/v1/messages/send" \
  -H "x-api-key: ${BRIDGE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "camp-demo-001",
    "lead_id": "lead-demo-001",
    "destination": {"telegram_user_id": "123456789"},
    "text": "Hello from mock test",
    "idempotency_key": "camp-demo-001-lead-demo-001-step0",
    "metadata": {"sequence_step": 0, "message_type": "cold_touch", "campaign_type": "cold"}
  }')"
echo "$SEND_JSON"

echo "[5/5] Simulating inbound reply event to n8n webhook..."
SIM_HTTP_CODE="$(curl -s -o /tmp/mock_sim.json -w "%{http_code}" -X POST "http://localhost:${BRIDGE_PORT:-8080}/v1/simulate/incoming" \
  -H "x-api-key: ${BRIDGE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"lead-demo-001","telegram_user_id":"123456789","text":"Can you share pricing?"}')"
if [[ "$SIM_HTTP_CODE" == "200" ]]; then
  cat /tmp/mock_sim.json
  echo ""
  echo "[PASS] Inbound event accepted by bridge."
else
  echo "[WARN] Inbound simulation did not reach active n8n webhook (HTTP ${SIM_HTTP_CODE})."
  cat /tmp/mock_sim.json
  echo ""
  echo "[INFO] Activate workflow '05 Inbound Listener' in n8n and rerun this script."
fi

echo ""
echo "Mock flow checks complete."
echo "Next in UI:"
echo "- Open n8n at http://localhost:${N8N_PORT:-5678}"
echo "- Ensure workflows are present (run: make import-workflows if missing)"
echo "- Configure credentials and activate workflow 05 to consume inbound events"
