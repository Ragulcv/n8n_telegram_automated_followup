#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
cd "$ROOT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FAIL] .env missing. Run: ./scripts/prepare_beginner_env.sh"
  exit 1
fi

API_ID=""
API_HASH=""
PHONE=""
SESSION=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/phase2_real_setup.sh [--api-id <id>] [--api-hash <hash>] [--phone <phone>] [--session <string>]

Notes:
  - If any value is omitted, you will be prompted.
  - This script switches to real Telegram mode and recreates n8n + bridge containers.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-id) API_ID="${2:-}"; shift 2 ;;
    --api-hash) API_HASH="${2:-}"; shift 2 ;;
    --phone) PHONE="${2:-}"; shift 2 ;;
    --session) SESSION="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[FAIL] Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

prompt_if_empty() {
  local var_name="$1"
  local prompt="$2"
  local current="$3"
  if [[ -n "$current" ]]; then
    printf '%s' "$current"
    return
  fi
  read -r -p "$prompt" value
  printf '%s' "$value"
}

API_ID="$(prompt_if_empty "API_ID" "TELEGRAM_API_ID: " "$API_ID")"
API_HASH="$(prompt_if_empty "API_HASH" "TELEGRAM_API_HASH: " "$API_HASH")"
PHONE="$(prompt_if_empty "PHONE" "TELEGRAM_PHONE (international format): " "$PHONE")"
SESSION="$(prompt_if_empty "SESSION" "TELEGRAM_SESSION_STRING: " "$SESSION")"

if [[ -z "$API_ID" || -z "$API_HASH" || -z "$PHONE" || -z "$SESSION" ]]; then
  echo "[FAIL] All values are required."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[FAIL] docker is not installed"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[FAIL] Docker daemon is not running"
  exit 1
fi

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

get_env() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d'=' -f2-
}

echo "[1/5] Writing real Telegram settings to .env..."
set_key TELEGRAM_MOCK_MODE "false"
set_key TELEGRAM_API_ID "$API_ID"
set_key TELEGRAM_API_HASH "$API_HASH"
set_key TELEGRAM_PHONE "$PHONE"
set_key TELEGRAM_SESSION_STRING "$SESSION"
set_key DAILY_SEND_CAP "10"
set_key OPS_NOTIFY_ENABLED "false"
set_key GSHEET_ENABLED "true"

echo "[2/5] Recreating containers (n8n + bridge) so env changes apply..."
docker compose up -d --force-recreate n8n bridge

echo "[3/5] Running preflight..."
"$ROOT_DIR/scripts/preflight_check.sh"

BRIDGE_PORT="$(get_env BRIDGE_PORT)"
BRIDGE_API_KEY="$(get_env BRIDGE_API_KEY)"
BRIDGE_PORT="${BRIDGE_PORT:-18080}"

echo "[4/5] Checking bridge health..."
curl -fsS "http://localhost:${BRIDGE_PORT}/health" >/dev/null
echo "[PASS] Bridge health OK"

echo "[5/5] Checking authenticated Telegram account health..."
curl -fsS -H "x-api-key: ${BRIDGE_API_KEY}" "http://localhost:${BRIDGE_PORT}/v1/account/health"
echo ""
echo "[PASS] Real mode setup completed."
echo ""
echo "Next commands:"
echo "1) ./scripts/phase2_stage_activate.sh --stage A"
echo "2) ./scripts/phase2_stage_activate.sh --stage B"
echo "3) ./scripts/phase2_stage_activate.sh --stage C"
echo "4) Keep stage D for after day-1 validation gate"
