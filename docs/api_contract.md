# Bridge API Contract

## Authentication

Header for all `/v1/*` endpoints:

- `x-api-key: <BRIDGE_API_KEY>`

## GET /v1/account/health

Response:

```json
{
  "status": "healthy",
  "connected": true,
  "daily_sent_count": 4,
  "daily_send_cap": 25,
  "warnings": []
}
```

## POST /v1/contacts/resolve

Request:

```json
{
  "campaign_id": "camp-001",
  "lead_id": "lead-001",
  "telegram_user_id": "",
  "username": "prospect_user"
}
```

Response:

```json
{
  "campaign_id": "camp-001",
  "lead_id": "lead-001",
  "telegram_user_id": "123456789",
  "username": "@prospect_user",
  "resolved": true
}
```

## POST /v1/messages/send

Request:

```json
{
  "campaign_id": "camp-001",
  "lead_id": "lead-001",
  "destination": {
    "telegram_user_id": "123456789",
    "username": ""
  },
  "text": "Hello",
  "idempotency_key": "camp-001-lead-001-step0",
  "metadata": {
    "sequence_step": 0,
    "message_type": "cold_touch",
    "campaign_type": "cold"
  }
}
```

Response:

```json
{
  "campaign_id": "camp-001",
  "lead_id": "lead-001",
  "idempotency_key": "camp-001-lead-001-step0",
  "result": {
    "status": "sent",
    "provider_message_id": "9012",
    "sent_at": "2026-03-04T16:15:00Z",
    "error_code": null
  }
}
```

## POST /v1/messages/send-batch

Request:

```json
{
  "messages": [
    {
      "campaign_id": "camp-001",
      "lead_id": "lead-001",
      "destination": {
        "telegram_user_id": "123456789"
      },
      "text": "Hello",
      "idempotency_key": "camp-001-lead-001-step0",
      "metadata": {
        "sequence_step": 0,
        "message_type": "cold_touch",
        "campaign_type": "cold"
      }
    }
  ]
}
```

## Bridge outbound event payload to n8n webhook

```json
{
  "event_id": "uuid",
  "event_type": "incoming_message",
  "timestamp": "2026-03-04T16:17:00Z",
  "lead_id": "lead-001",
  "telegram_user_id": "123456789",
  "message_id": "9020",
  "text": "Can you share pricing?",
  "raw": {}
}
```
