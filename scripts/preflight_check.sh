#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

pass() { echo "[PASS] $1"; }
warn() { echo "[WARN] $1"; }
fail() { echo "[FAIL] $1"; }

require_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "Command available: $cmd"
  else
    fail "Missing command: $cmd"
  fi
}

if [[ ! -f "$ENV_FILE" ]]; then
  fail ".env missing. Run: ./scripts/prepare_beginner_env.sh"
  exit 1
fi
pass ".env exists"

get_env() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d'=' -f2-
}

require_cmd docker
require_cmd curl
require_cmd python3

if docker info >/dev/null 2>&1; then
  pass "Docker daemon is running"
else
  fail "Docker daemon is not running"
fi

check_required_real() {
  local key="$1"
  local value
  value="$(get_env "$key")"
  if [[ -z "$value" || "$value" == replace-with-* || "$value" == "change-me" || "$value" == "Your Name" || "$value" == "123456" || "$value" == "+971500000000" || "$value" == "-100123456789" ]]; then
    warn "$key is not set with a real value"
  else
    pass "$key is set"
  fi
}

check_required_real N8N_ENCRYPTION_KEY
check_required_real BRIDGE_API_KEY
check_required_real SESSION_ENCRYPTION_KEY
if [[ "$(get_env GSHEET_ENABLED)" == "true" ]]; then
  check_required_real GSHEET_ID
else
  pass "GSHEET_ENABLED=false (Google Sheets optional for phase-1 tests)"
fi

if [[ "$(get_env OPS_NOTIFY_ENABLED)" == "true" ]]; then
  check_required_real OPS_BOT_TOKEN
  check_required_real OPS_CHAT_ID
else
  pass "OPS_NOTIFY_ENABLED=false (ops bot credentials optional for now)"
fi

if [[ "$(get_env TELEGRAM_MOCK_MODE)" == "true" ]]; then
  pass "TELEGRAM_MOCK_MODE=true (safe for testing)"
else
  warn "TELEGRAM_MOCK_MODE=false (real Telegram sends possible)"
  check_required_real TELEGRAM_API_ID
  check_required_real TELEGRAM_API_HASH
  check_required_real TELEGRAM_PHONE
  if [[ -z "$(get_env TELEGRAM_SESSION_STRING)" ]]; then
    warn "TELEGRAM_SESSION_STRING is empty"
  else
    pass "TELEGRAM_SESSION_STRING is set"
  fi
fi

echo ""
echo "Preflight completed."
