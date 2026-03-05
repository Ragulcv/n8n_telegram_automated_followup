# n8n Telegram Outreach Automation (Simplified v3)

This project now runs a refactored **2-workflow** setup:

1. `TG Outreach - Draft & Approve`
2. `TG Outreach - Send & Monitor`

It reuses your existing stack:
- `n8n` (Docker)
- `telegram-bridge` (personal Telegram account sending/inbound)
- `Google Sheets` (`Leads` + hidden `SystemState` + hidden `OpsAudit`)
- Ops Telegram bot for approvals/alerts

## What is live now

- Only the two refactored workflows are active.
- Legacy `01..08` JSON files are archived in `n8n/workflows/archive/`.
- Draft approval cards include `lead_id` and inline buttons.
- Ops commands supported:
  - `approve <lead_id>`
  - `edit <lead_id> <feedback>`
  - `skip <lead_id>`
  - `dnc <lead_id>`
  - `/draftnow`

## Quick start (from project root)

```bash
cd "/Users/ragul/Applications/codex projects/n8n project for telegram outreach "
docker compose up -d
make import-workflows
```

Then ensure these 2 workflows are published in n8n:
- `wf_tg_outreach_draft_approve`
- `wf_tg_outreach_send_monitor`

## Google Sheets contract

Business tracker tab:
- `Leads`

`Leads` required columns (minimal):
- `lead_id`
- `name`
- `telegram_username`
- `company`
- `role`
- `source_url`
- `status`
- `last_contacted_at`
- `next_followup_at`
- `followup_count`

Hidden system tabs:
- `SystemState` columns:
  - `lead_id`, `telegram_chat_id`, `draft_message`, `research_snippet`, `memory_summary`, `approval_feedback`, `last_reply_received`, `last_reply_at`, `last_idempotency_key`, `last_sent_type`, `last_error`, `last_error_at`, `message_history`, `updated_at`
- `OpsAudit` columns:
  - `event_at`, `lead_id`, `event_type`, `actor`, `details`

`Leads.status` dropdown values:
- `NEW`
- `NEEDS_APPROVAL`
- `APPROVED`
- `SENT`
- `REPLIED`
- `FOLLOWUP_DUE`
- `NOT_INTERESTED`
- `DNC`
- `FAILED`

Templates:
- `sheets/templates/Leads.csv`
- `sheets/seed/Leads.csv`
- `sheets/templates/SystemState.csv`
- `sheets/seed/SystemState.csv`
- `sheets/templates/OpsAudit.csv`
- `sheets/seed/OpsAudit.csv`

## How to operate (beginner flow)

1. Add lead rows in `Leads` with `status=NEW`.
2. Trigger draft generation:
   - Automatic: daily at `10:00` Dubai.
   - Manual from Ops bot chat: `/draftnow`.
   - Manual webhook:
     ```bash
     curl -X POST http://localhost:15678/webhook/tg-outreach/draft-now \
       -H "Content-Type: application/json" \
       -d '{}'
     ```
3. Approval card arrives in Ops chat with buttons.
4. Approve/edit/skip/dnc via button or text command.
5. Send engine (every 30 min) sends only rows with:
   - `status=APPROVED`
6. Inbound lead replies auto-update sheet and notify Ops immediately.
7. Daily summary posts at `20:00` Dubai.

## Guardrails enabled

- No outbound send without manual approval (`APPROVED + Y`).
- `DNC` / `NOT_INTERESTED` stop future outreach.
- Daily cap: `DAILY_SEND_CAP` (default 10).
- Random send delay: `SEND_DELAY_MIN_SECONDS..SEND_DELAY_MAX_SECONDS` (default 180..600).
- Follow-up interval randomization: `FOLLOWUP_MIN_DAYS..FOLLOWUP_MAX_DAYS` (default 2..3).

## Environment variables used

Core:
- `GSHEET_ID`
- `BRIDGE_BASE_URL`
- `BRIDGE_API_KEY`
- `OPS_BOT_TOKEN`
- `OPS_CHAT_ID`
- `OPENAI_API_KEY`

Behavior:
- `OUTREACH_SENDER_NAME`
- `OUTREACH_SYSTEM_PROMPT`
- `DAILY_SEND_CAP`
- `SEND_DELAY_MIN_SECONDS`
- `SEND_DELAY_MAX_SECONDS`
- `FOLLOWUP_MIN_DAYS`
- `FOLLOWUP_MAX_DAYS`
- `MAX_FOLLOWUPS`
- `OPS_NOTIFY_ENABLED`

## Smoke tests

Draft + approval card:
```bash
curl -X POST http://localhost:15678/webhook/tg-outreach/draft-now \
  -H "Content-Type: application/json" \
  -d '{}'
```

Inbound simulation through bridge:
```bash
curl -X POST http://localhost:18080/v1/simulate/incoming \
  -H "x-api-key: $(grep '^BRIDGE_API_KEY=' .env | cut -d'=' -f2-)" \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"lead-test-01","telegram_user_id":"123456789","text":"Can we discuss pricing and demo?"}'
```

## Expected outcomes

- `Draft & Approve` execution succeeds.
- `Leads` rows move to `NEEDS_APPROVAL`.
- `SystemState` receives generated `draft_message`/`research_snippet`.
- Ops chat receives approval cards with inline actions.
- Inbound simulation triggers `Send & Monitor` success and updates:
  - `Leads.status`
  - `SystemState.last_reply_received`/`memory_summary`.

## Workflow docs

- `n8n/workflows/README.md`
