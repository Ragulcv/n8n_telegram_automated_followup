# n8n Workflow Import Guide (Refactor v2)

## Active workflow files

1. `10_tg_outreach_draft_approve.json`
2. `11_tg_outreach_send_monitor.json`

Legacy files `01..08` are archived under `n8n/workflows/archive/`.

## Import

```bash
cd "/Users/ragul/Applications/codex projects/n8n project for telegram outreach "
make import-workflows
```

Publish both workflows in n8n after import.

## Trigger model

### Workflow A: Draft & Approve
- Daily schedule at 10:00 Dubai
- Manual trigger
- Webhook: `POST /webhook/tg-outreach/draft-now`

### Workflow B: Send & Monitor
- Sending engine: every 30 min
- Inbound webhook: `POST /webhook/telegram/events`
- Ops command polling: every 1 min via Telegram Bot `getUpdates`
- Daily summary: 20:00 Dubai

## Required env vars

- `GSHEET_ID`
- `BRIDGE_BASE_URL`
- `BRIDGE_API_KEY`
- `OPS_BOT_TOKEN`
- `OPS_CHAT_ID`
- `OPENAI_API_KEY`
- `OUTREACH_SENDER_NAME`
- `OUTREACH_SYSTEM_PROMPT`
- `DAILY_SEND_CAP`
- `SEND_DELAY_MIN_SECONDS`
- `SEND_DELAY_MAX_SECONDS`
- `FOLLOWUP_MIN_DAYS`
- `FOLLOWUP_MAX_DAYS`
- `MAX_FOLLOWUPS`

## Required credentials in n8n

- Google Sheets OAuth2 credential
- Telegram credential (Ops bot) for send/ack nodes

## Bridge webhook target

Bridge posts inbound events to:
- `POST /webhook/telegram/events`

Default internal compose URL is already expected via `N8N_EVENTS_WEBHOOK_URL=http://n8n:5678/webhook/telegram/events`.
