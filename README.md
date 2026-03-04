# n8n Telegram Outreach Automation

Beginner-friendly setup for sector-agnostic Telegram outreach with:

- n8n orchestration
- Telegram user-account bridge (Telethon, with mock mode)
- Google Sheets lead tracking
- Human-in-the-loop approvals in Telegram ops chat

## Current status (already done in this workspace)

- Project scaffolding created
- Bridge implemented and tested
- Docker stack starts successfully
- Workflows imported into n8n (`wf_01` to `wf_08`)
- Mock end-to-end bridge test passed

## Fast path for beginners

Run these commands in order from the project root:

```bash
cd "/Users/ragul/Applications/codex projects/n8n project for telegram outreach "
make prepare-env
make preflight
make test-mock
make import-workflows
```

## What each command does

- `make prepare-env`
  - Creates/updates `.env`
  - Generates secure defaults for local testing
  - Auto-adjusts host ports if conflicts exist
- `make preflight`
  - Checks required tools and config
  - Shows exactly which values are still missing
- `make test-mock`
  - Starts `n8n + bridge + redis`
  - Runs bridge health checks
  - Sends one mock outbound message
  - Simulates one inbound reply event
- `make import-workflows`
  - Imports all workflow JSON files into n8n automatically

## Open the app

- n8n UI: `http://localhost:$(grep '^N8N_PORT=' .env | cut -d'=' -f2-)`
- Bridge health: `http://localhost:$(grep '^BRIDGE_PORT=' .env | cut -d'=' -f2-)/health`

## What you still need to configure

In [`.env`](./.env), replace placeholders for:

- `GSHEET_ID`

For beginner testing, keep:

- `OPS_NOTIFY_ENABLED=false` (default) so ops-bot credentials are optional.

When you want Telegram ops notifications enabled, then set:

- `OPS_NOTIFY_ENABLED=true`
- `OPS_BOT_TOKEN`
- `OPS_CHAT_ID`

For real Telegram sending later (production mode):

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_PHONE`
- `TELEGRAM_SESSION_STRING`
- set `TELEGRAM_MOCK_MODE=false`

## Phase 2 (real Telegram go-live, staged)

This repository now includes phase-2 helper scripts:

1. Real-mode setup (prompts for Telegram credentials and recreates containers):
```bash
cd "/Users/ragul/Applications/codex projects/n8n project for telegram outreach "
make phase2-real-setup
```

2. Staged workflow activation:
```bash
make phase2-stage-a
make phase2-stage-b
make phase2-stage-c
# run stage D only after day-1 validation gate passes
# make phase2-stage-d
```

3. Day-1 gate checklist command:
```bash
make phase2-gate
```

4. Quick active-workflow status:
```bash
make phase2-status
```

Phase-2 defaults enforced by setup script:
- `DAILY_SEND_CAP=10`
- `OPS_NOTIFY_ENABLED=false`
- `GSHEET_ENABLED=true`
- `TELEGRAM_MOCK_MODE=false` (after real creds are provided)

## Phase 3 (ops bot + approval and reporting live)

Once phase-2 is stable and your Google Sheets are updating correctly, set these in `.env`:

- `OPS_BOT_TOKEN=<real bot token from BotFather>`
- `OPS_CHAT_ID=<real group/chat id where bot is added>`

Then run:

```bash
cd "/Users/ragul/Applications/codex projects/n8n project for telegram outreach "
make phase3-ops-setup
```

What this command does:
- Creates/updates Telegram bot credential in n8n
- Binds Telegram credential for workflows `05`, `06`, `07`, `08`
- Forces `05` to notify ops group when `OPS_NOTIFY_ENABLED=true`
- Sets `OPS_NOTIFY_ENABLED=true` in `.env`
- Recreates containers and activates workflows `01..08`
- Sends a test bot message to your ops chat

## Exact testing flow (beginner)

1. Keep `TELEGRAM_MOCK_MODE=true`.
2. Run `make preflight` and confirm only Google/ops values are warnings.
3. Open n8n UI.
4. Verify workflows exist:
   - `01 Campaign Intake`
   - `02 Lead Qualification + Enrichment`
   - `03 Send Orchestrator`
   - `04 Follow-Up Scheduler`
   - `05 Inbound Listener`
   - `06 Human Approval`
   - `07 Daily Reporting`
   - `08 Reconciliation + Exceptions`
5. Configure credentials in n8n:
   - Google Sheets OAuth2
   - Telegram Bot (ops bot)
6. Activate workflow `05 Inbound Listener`.
7. Trigger inbound simulation:

```bash
curl -X POST http://localhost:18080/v1/simulate/incoming \
  -H "x-api-key: $(grep '^BRIDGE_API_KEY=' .env | cut -d'=' -f2-)" \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"lead-demo-001","telegram_user_id":"123456789","text":"Can you share pricing?"}'
```

8. Confirm results:
   - n8n execution appears in workflow 05
   - A new row is created in `Replies`
   - A new row is created in `Approvals`
   - Ops Telegram receives notification

## Give me feedback template

After you run steps, send this back to me:

```text
STEP 1 (preflight): PASS/FAIL
STEP 2 (containers): PASS/FAIL
STEP 3 (n8n UI open): PASS/FAIL
STEP 4 (workflows visible): PASS/FAIL
STEP 5 (credentials set): PASS/FAIL
STEP 6 (inbound simulation): PASS/FAIL
Observed error message (if any):
Screenshot/log snippet:
```

I will then fix any failing step and continue with you until production-ready.

## Additional docs

- API contract: [`docs/api_contract.md`](docs/api_contract.md)
- Ops runbook: [`docs/operations.md`](docs/operations.md)
- Workflow import notes: [`n8n/workflows/README.md`](n8n/workflows/README.md)
