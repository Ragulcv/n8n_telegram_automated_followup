# Operations Runbook

## Startup checklist

1. Ensure dedicated outreach account has valid session.
2. Verify bridge health endpoint:

```bash
curl http://localhost:8080/health
```

3. Verify authenticated account health:

```bash
curl -H "x-api-key: $BRIDGE_API_KEY" http://localhost:8080/v1/account/health
```

4. Phase-2 staged activation order:
   - Stage A: 01 + 05
   - Stage B: 01 + 02 + 03 + 05
   - Stage C: 01 + 02 + 03 + 05 + 08
   - Stage D (after day-1 gate): 01 + 02 + 03 + 04 + 05 + 08
   - Keep OFF in phase-2: 06, 07

## Phase-3 ops activation

After phase-2 stability is confirmed, enable ops bot and reporting:

1. Set real values in `.env`:
   - `OPS_BOT_TOKEN`
   - `OPS_CHAT_ID`
2. Run:
   ```bash
   ./scripts/phase3_ops_setup.sh
   ```
3. Confirm active workflows include `06 Human Approval` and `07 Daily Reporting`.
4. In ops chat, run `/claim <task_id>` on a fresh approval row and verify:
   - `Approvals` gets audit append row
   - `DNC` appends if `/dnc` or `/not_interested`

## Safety checks

- Start phase-2 with `DAILY_SEND_CAP=10`.
- Keep `OPS_NOTIFY_ENABLED=false` unless ops bot credentials are fully configured.
- Enable `TELEGRAM_MOCK_MODE=false` only after valid real session string is set.
- Monitor `warnings` from account health.
- Do not raise `DAILY_SEND_CAP` abruptly.
- Keep DNC tab immutable except append operations.

## Incident handling

### Rate limit / flood wait

1. Disable `03_send_orchestrator` and `04_followup_scheduler`.
2. Review bridge warnings and logs.
3. Lower `DAILY_SEND_CAP` and resume gradually.

### Missing inbound events

1. Verify `N8N_EVENTS_WEBHOOK_URL` in bridge env.
2. Check n8n webhook URL in workflow 05 (test vs production URL).
3. Use simulation endpoint:

```bash
curl -X POST http://localhost:8080/v1/simulate/incoming \
  -H "x-api-key: $BRIDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"lead-123","telegram_user_id":"12345","text":"pricing?"}'
```

## SLA reminders

Workflow 06 uses approval command processing. For pending tasks past SLA, use workflow 08 alerts and manual reminders in ops chat.
