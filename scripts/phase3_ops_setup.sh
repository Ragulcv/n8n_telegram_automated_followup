#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
cd "$ROOT_DIR"

OPS_CRED_ID="opsTelegramBotV1"
OPS_CRED_NAME="Ops Telegram Bot"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FAIL] .env missing. Run: ./scripts/prepare_beginner_env.sh"
  exit 1
fi

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[FAIL] Missing command: $cmd"
    exit 1
  fi
}

get_env() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d'=' -f2-
}

set_key() {
  local key="$1"
  local value="$2"
  awk -v k="$key" -v v="$value" '
    BEGIN { done = 0 }
    $0 ~ "^"k"=" {
      print k"="v
      done = 1
      next
    }
    { print }
    END {
      if (!done) print k"="v
    }
  ' "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
}

is_placeholder() {
  local v="$1"
  [[ -z "$v" || "$v" == replace-with-* || "$v" == "-100123456789" ]]
}

require_cmd docker
require_cmd jq
require_cmd curl

if ! docker info >/dev/null 2>&1; then
  echo "[FAIL] Docker daemon is not running"
  exit 1
fi

OPS_BOT_TOKEN="$(get_env OPS_BOT_TOKEN)"
OPS_CHAT_ID="$(get_env OPS_CHAT_ID)"

if is_placeholder "$OPS_BOT_TOKEN"; then
  echo "[FAIL] OPS_BOT_TOKEN is not set with a real bot token in .env"
  exit 1
fi

if is_placeholder "$OPS_CHAT_ID"; then
  echo "[FAIL] OPS_CHAT_ID is not set with a real Telegram chat id in .env"
  exit 1
fi

echo "[1/8] Exporting existing credentials to locate Google Sheets credential..."
docker compose exec -T n8n n8n export:credentials --all --output=/tmp/phase3_creds.json >/tmp/phase3_export_creds.log
docker compose exec -T n8n sh -lc 'cat /tmp/phase3_creds.json' > /tmp/phase3_creds.json

GSHEET_CRED_ID="$(jq -r '.[] | select(.type=="googleSheetsOAuth2Api") | .id' /tmp/phase3_creds.json | head -n1)"
if [[ -z "$GSHEET_CRED_ID" ]]; then
  echo "[FAIL] Could not find Google Sheets credential in n8n. Create it first in n8n UI."
  exit 1
fi
echo "[PASS] Found Google Sheets credential id: $GSHEET_CRED_ID"

echo "[2/8] Creating/updating Telegram bot credential in n8n..."
cat > /tmp/phase3_ops_cred.json <<JSON
[
  {
    "id": "$OPS_CRED_ID",
    "name": "$OPS_CRED_NAME",
    "type": "telegramApi",
    "data": {
      "accessToken": "$OPS_BOT_TOKEN",
      "baseUrl": "https://api.telegram.org"
    }
  }
]
JSON
docker compose cp /tmp/phase3_ops_cred.json n8n:/tmp/phase3_ops_cred.json >/dev/null
docker compose exec -T n8n n8n import:credentials --input=/tmp/phase3_ops_cred.json >/tmp/phase3_import_cred.log
echo "[PASS] Telegram bot credential imported/updated"

patch_workflow() {
  local in_file="$1"
  local out_file="$2"
  jq \
    --arg gsid "$GSHEET_CRED_ID" \
    --arg tgid "$OPS_CRED_ID" \
    --arg tgname "$OPS_CRED_NAME" \
    '
      .nodes |= map(
        if (.credentials.googleSheetsOAuth2Api? != null) then
          .credentials.googleSheetsOAuth2Api.id = $gsid
          | .credentials.googleSheetsOAuth2Api.name = "Google Sheets"
        else . end
        | if (.credentials.telegramApi? != null) then
            .credentials.telegramApi.id = $tgid
            | .credentials.telegramApi.name = $tgname
          else . end
      )
      | if .id == "wf_05_inbound_listener" then
          .connections["Ops Notify Enabled?"].main[0] = [{"node":"Notify Ops Group","type":"main","index":0}]
          | .connections["Ops Notify Enabled?"].main[1] = [{"node":"Respond 200","type":"main","index":0}]
          | .connections["Notify Ops Group"].main = [[{"node":"Respond 200","type":"main","index":0}]]
        else . end
    ' "$in_file" > "$out_file"
}

echo "[3/8] Patching workflow credentials and ops-notify route..."
WF_FILES=(
  "05_inbound_listener.json"
  "06_human_approval.json"
  "07_daily_reporting.json"
  "08_reconciliation_exceptions.json"
)
for wf in "${WF_FILES[@]}"; do
  patch_workflow "$ROOT_DIR/n8n/workflows/$wf" "/tmp/$wf.phase3.json"
done
echo "[PASS] Workflow patch files created"

echo "[4/8] Importing patched workflows into n8n..."
for wf in "${WF_FILES[@]}"; do
  docker compose cp "/tmp/$wf.phase3.json" "n8n:/tmp/$wf.phase3.json" >/dev/null
  docker compose exec -T n8n n8n import:workflow --input="/tmp/$wf.phase3.json" >/tmp/phase3_import_wf.log
done
echo "[PASS] Patched workflows imported"

echo "[5/8] Enabling OPS_NOTIFY flag in .env..."
set_key OPS_NOTIFY_ENABLED "true"
echo "[PASS] OPS_NOTIFY_ENABLED=true"

echo "[6/8] Recreating containers to load new env..."
docker compose up -d --force-recreate n8n bridge >/tmp/phase3_recreate.log

echo "[7/8] Activating workflows (phase-2 + ops/reporting)..."
"$ROOT_DIR/scripts/phase2_stage_activate.sh" --stage D >/tmp/phase3_stage_d.log
docker compose exec -T n8n n8n publish:workflow --id=wf_06_human_approval >/dev/null
docker compose exec -T n8n n8n publish:workflow --id=wf_07_daily_reporting >/dev/null
docker compose restart n8n >/tmp/phase3_restart.log
echo "[PASS] Workflows 01..08 are activated"

echo "[8/8] Running health checks..."
BRIDGE_PORT="$(get_env BRIDGE_PORT)"
BRIDGE_API_KEY="$(get_env BRIDGE_API_KEY)"
BRIDGE_PORT="${BRIDGE_PORT:-18080}"
curl -fsS "http://localhost:${BRIDGE_PORT}/health" >/dev/null
curl -fsS -H "x-api-key: ${BRIDGE_API_KEY}" "http://localhost:${BRIDGE_PORT}/v1/account/health" >/dev/null

BOT_GETME="$(curl -fsS "https://api.telegram.org/bot${OPS_BOT_TOKEN}/getMe" || true)"
if [[ "$BOT_GETME" == *'"ok":true'* ]]; then
  echo "[PASS] Telegram bot token is valid (getMe succeeded)"
else
  echo "[WARN] Telegram bot getMe failed. Check OPS_BOT_TOKEN."
fi

BOT_SEND="$(curl -fsS -X POST "https://api.telegram.org/bot${OPS_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${OPS_CHAT_ID}" \
  --data-urlencode "text=n8n ops phase-3 setup completed. Approval and digest workflows are active." || true)"
if [[ "$BOT_SEND" == *'"ok":true'* ]]; then
  echo "[PASS] Test message sent to OPS chat"
else
  echo "[WARN] Could not send test message to OPS chat. Add bot to group and verify OPS_CHAT_ID."
fi

echo ""
echo "Phase-3 ops setup completed."
echo "Active workflows:"
docker compose exec -T n8n n8n list:workflow --active=true
