#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
EXAMPLE_FILE="$ROOT_DIR/.env.example"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo "Created .env from .env.example"
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

current_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d'=' -f2-
}

port_in_use() {
  local port="$1"
  lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1
}

is_placeholder() {
  local value="$1"
  [[ -z "$value" || "$value" == replace-with-* || "$value" == "change-me" || "$value" == "Your Name" || "$value" == "123456" || "$value" == "+971500000000" ]]
}

rand_hex() {
  local len="$1"
  openssl rand -hex "$len"
}

n8n_key="$(current_value N8N_ENCRYPTION_KEY || true)"
if is_placeholder "$n8n_key"; then
  set_key N8N_ENCRYPTION_KEY "$(rand_hex 16)"
fi

bridge_key="$(current_value BRIDGE_API_KEY || true)"
if is_placeholder "$bridge_key"; then
  set_key BRIDGE_API_KEY "$(rand_hex 24)"
fi

basic_pass="$(current_value N8N_BASIC_AUTH_PASSWORD || true)"
if is_placeholder "$basic_pass"; then
  set_key N8N_BASIC_AUTH_PASSWORD "$(rand_hex 8)"
fi

session_key="$(current_value SESSION_ENCRYPTION_KEY || true)"
if is_placeholder "$session_key"; then
  set_key SESSION_ENCRYPTION_KEY "$(python3 "$ROOT_DIR/scripts/generate_fernet_key.py")"
fi

sender_name="$(current_value OUTREACH_SENDER_NAME || true)"
if is_placeholder "$sender_name" || [[ "$sender_name" == *" "* ]]; then
  set_key OUTREACH_SENDER_NAME "OutreachTeam"
fi

set_key TELEGRAM_MOCK_MODE "true"
set_key GSHEET_ENABLED "false"

n8n_port="$(current_value N8N_PORT || true)"
if [[ -z "$n8n_port" ]]; then
  n8n_port="5678"
fi
if port_in_use "$n8n_port"; then
  n8n_port="15678"
  set_key N8N_PORT "$n8n_port"
  set_key N8N_EDITOR_BASE_URL "http://localhost:${n8n_port}"
  set_key WEBHOOK_URL "http://localhost:${n8n_port}"
fi

bridge_port="$(current_value BRIDGE_PORT || true)"
if [[ -z "$bridge_port" ]]; then
  bridge_port="8080"
fi
if port_in_use "$bridge_port"; then
  bridge_port="18080"
  set_key BRIDGE_PORT "$bridge_port"
fi

echo "Prepared .env with secure local defaults."
echo "n8n URL: http://localhost:$(current_value N8N_PORT)"
echo "n8n user: $(current_value N8N_BASIC_AUTH_USER)"
echo "n8n password: $(current_value N8N_BASIC_AUTH_PASSWORD)"
echo "bridge URL: http://localhost:$(current_value BRIDGE_PORT)"
echo ""
echo "Next: fill these required real values before full workflow testing:"
echo "- GSHEET_ID"
echo "- OPS_BOT_TOKEN"
echo "- OPS_CHAT_ID"
echo ""
echo "Optional now (only for real Telegram sending mode):"
echo "- TELEGRAM_API_ID"
echo "- TELEGRAM_API_HASH"
echo "- TELEGRAM_PHONE"
echo "- TELEGRAM_SESSION_STRING"
