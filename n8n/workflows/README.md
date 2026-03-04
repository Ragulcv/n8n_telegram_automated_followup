# n8n Workflow Import Guide

## Files

1. `01_campaign_intake.json`
2. `02_lead_qualification_enrichment.json`
3. `03_send_orchestrator.json`
4. `04_followup_scheduler.json`
5. `05_inbound_listener.json`
6. `06_human_approval.json`
7. `07_daily_reporting.json`
8. `08_reconciliation_exceptions.json`

## Import order

Import in numeric order and keep workflows disabled until all credentials are set.

## Required environment variables in n8n

- `GSHEET_ID`
- `BRIDGE_BASE_URL`
- `BRIDGE_API_KEY`
- `OPS_CHAT_ID`
- `APPROVAL_SLA_MINUTES`
- `DELIVERY_RETRY_DELAYS`
- `OUTREACH_SENDER_NAME`

## Required credentials in n8n

- Google Sheets OAuth2 credential
- Telegram Bot credential (ops bot)

After import, replace `REPLACE_ME` placeholder IDs in each node credential block.

## Webhook registration

Workflow `05_inbound_listener.json` exposes:

- `POST /webhook/telegram/events`

Set `N8N_EVENTS_WEBHOOK_URL` in bridge `.env` to this endpoint (internal compose URL is already defaulted).
