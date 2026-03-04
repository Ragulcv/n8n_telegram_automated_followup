#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAGE=""
EXECUTE_ONCE="false"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/phase2_stage_activate.sh --stage <A|B|C|D|status> [--execute-once]

Stage map:
  A: Activate 01 + keep 05 active
  B: Activate 01, 02, 03 + keep 05 active
  C: Activate 01, 02, 03, 08 + keep 05 active
  D: Activate 01, 02, 03, 04, 08 + keep 05 active

Always OFF in phase-2:
  06 Human Approval
  07 Daily Reporting
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage) STAGE="${2:-}"; shift 2 ;;
    --execute-once) EXECUTE_ONCE="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[FAIL] Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$STAGE" ]]; then
  echo "[FAIL] --stage is required"
  usage
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[FAIL] Docker daemon is not running"
  exit 1
fi

if ! docker compose ps n8n >/dev/null 2>&1; then
  echo "[FAIL] n8n container is not running. Run: docker compose up -d"
  exit 1
fi

ALL_IDS=(
  "wf_01_campaign_intake"
  "wf_02_lead_qualification_enrichment"
  "wf_03_send_orchestrator"
  "wf_04_followup_scheduler"
  "wf_05_inbound_listener"
  "wf_06_human_approval"
  "wf_07_daily_reporting"
  "wf_08_reconciliation_exceptions"
)

desired_ids_for_stage() {
  local s="$1"
  case "$s" in
    A|a) echo "wf_01_campaign_intake wf_05_inbound_listener" ;;
    B|b) echo "wf_01_campaign_intake wf_02_lead_qualification_enrichment wf_03_send_orchestrator wf_05_inbound_listener" ;;
    C|c) echo "wf_01_campaign_intake wf_02_lead_qualification_enrichment wf_03_send_orchestrator wf_05_inbound_listener wf_08_reconciliation_exceptions" ;;
    D|d) echo "wf_01_campaign_intake wf_02_lead_qualification_enrichment wf_03_send_orchestrator wf_04_followup_scheduler wf_05_inbound_listener wf_08_reconciliation_exceptions" ;;
    status) echo "__STATUS_ONLY__" ;;
    *)
      echo ""
      ;;
  esac
}

DESIRED="$(desired_ids_for_stage "$STAGE")"
if [[ -z "$DESIRED" ]]; then
  echo "[FAIL] Invalid stage: $STAGE"
  usage
  exit 1
fi

if [[ "$DESIRED" != "__STATUS_ONLY__" ]]; then
  echo "[1/3] Updating active workflows for stage $STAGE..."
  for wf in "${ALL_IDS[@]}"; do
    if [[ " $DESIRED " == *" $wf "* ]]; then
      echo "  + publish $wf"
      docker compose exec -T n8n n8n publish:workflow --id="$wf" >/dev/null
    else
      echo "  - unpublish $wf"
      docker compose exec -T n8n n8n unpublish:workflow --id="$wf" >/dev/null || true
    fi
  done

  echo "[2/3] Restarting n8n to apply publish/unpublish changes..."
  docker compose restart n8n >/dev/null
fi

echo "[3/3] Current workflow active states:"
docker compose exec -T n8n n8n export:workflow --all --output=/tmp/all_stage_state.json >/tmp/export_stage_state.log
docker compose exec -T n8n sh -lc 'cat /tmp/all_stage_state.json' > /tmp/all_stage_state.json
python3 - <<'PY'
import json
arr=json.load(open('/tmp/all_stage_state.json'))
for w in arr:
    print(f"{w['id']}\t{w['name']}\tactive={w.get('active')}")
PY

if [[ "$EXECUTE_ONCE" == "true" && "$DESIRED" != "__STATUS_ONLY__" ]]; then
  echo ""
  echo "[Run once] Executing active stage workflows one time..."
  case "$STAGE" in
    A|a)
      docker compose exec -T n8n n8n execute --id=wf_01_campaign_intake >/dev/null || true
      ;;
    B|b)
      docker compose exec -T n8n n8n execute --id=wf_01_campaign_intake >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_02_lead_qualification_enrichment >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_03_send_orchestrator >/dev/null || true
      ;;
    C|c)
      docker compose exec -T n8n n8n execute --id=wf_01_campaign_intake >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_02_lead_qualification_enrichment >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_03_send_orchestrator >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_08_reconciliation_exceptions >/dev/null || true
      ;;
    D|d)
      docker compose exec -T n8n n8n execute --id=wf_01_campaign_intake >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_02_lead_qualification_enrichment >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_03_send_orchestrator >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_04_followup_scheduler >/dev/null || true
      docker compose exec -T n8n n8n execute --id=wf_08_reconciliation_exceptions >/dev/null || true
      ;;
  esac
  echo "[PASS] One-time execution run completed."
fi
