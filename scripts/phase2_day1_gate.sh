#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
cd "$ROOT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FAIL] .env missing"
  exit 1
fi

get_env() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d'=' -f2-
}

BRIDGE_PORT="$(get_env BRIDGE_PORT)"
BRIDGE_API_KEY="$(get_env BRIDGE_API_KEY)"
BRIDGE_PORT="${BRIDGE_PORT:-18080}"

echo "[1/4] Bridge account health"
curl -fsS -H "x-api-key: ${BRIDGE_API_KEY}" "http://localhost:${BRIDGE_PORT}/v1/account/health"
echo ""

echo "[2/4] Active workflow snapshot"
docker compose exec -T n8n n8n export:workflow --all --output=/tmp/all_gate_state.json >/tmp/export_gate_state.log
docker compose exec -T n8n sh -lc 'cat /tmp/all_gate_state.json' > /tmp/all_gate_state.json
python3 - <<'PY'
import json
arr=json.load(open('/tmp/all_gate_state.json'))
for w in arr:
    print(f"{w['id']}\t{w['name']}\tactive={w.get('active')}")
PY

echo "[3/4] Recent bridge warnings/errors (last 50 lines)"
docker compose logs --tail=50 bridge

echo "[4/4] Reminder checks in Google Sheets"
echo "- Verify Queue, MessageLog, Replies, Approvals all have fresh rows"
echo "- Verify no obvious duplicate queue/send rows for same lead + sequence step"
echo "- If clean, you can enable stage D:"
echo "  ./scripts/phase2_stage_activate.sh --stage D"
