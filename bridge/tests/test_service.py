from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.schemas import Destination, ResolveContactRequest, SendMessageRequest, SendMetadata
from app.service import BridgeService
from app.telegram_client import ResolveResult


class FakeStorage:
    def __init__(self):
        self.idempotency = {}
        self.daily_sent = 0
        self.last_error = None

    async def connect(self):
        return None

    async def close(self):
        return None

    async def get_idempotency(self, key):
        return self.idempotency.get(key)

    async def set_idempotency(self, key, payload, ttl_seconds):
        _ = ttl_seconds
        self.idempotency[key] = payload

    async def get_daily_sent(self, account_key):
        _ = account_key
        return self.daily_sent

    async def increment_daily_sent(self, account_key):
        _ = account_key
        self.daily_sent += 1
        return self.daily_sent

    async def set_last_error(self, message):
        self.last_error = message

    async def get_last_error(self):
        return self.last_error

    async def get_encrypted_session(self):
        return None

    async def set_encrypted_session(self, encrypted_session):
        _ = encrypted_session
        return None


class FakePublisher:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)


class FakeTelegramClient:
    def __init__(self):
        self.connected = True

    async def connect(self):
        return None

    async def close(self):
        return None

    def set_incoming_handler(self, handler):
        _ = handler

    async def send_message(self, telegram_user_id, username, text):
        _ = telegram_user_id, username, text
        return "msg-1"

    async def resolve_contact(self, telegram_user_id, username):
        if telegram_user_id:
            return ResolveResult(telegram_user_id=telegram_user_id, username=username, resolved=True)
        return ResolveResult(telegram_user_id=None, username="@alice", resolved=True)


@pytest.mark.asyncio
async def test_send_message_idempotent():
    settings = Settings(
        BRIDGE_API_KEY="x",
        TELEGRAM_MOCK_MODE=True,
        SESSION_ENCRYPTION_KEY="dGVzdGtleWRHVnpkR3RsZVdSbGN3PT0=",
        N8N_EVENTS_WEBHOOK_URL="http://localhost",
        REDIS_URL="redis://localhost:6379/0",
    )
    service = BridgeService(settings)
    service.storage = FakeStorage()
    service.publisher = FakePublisher()
    service.telegram_client = FakeTelegramClient()

    request = SendMessageRequest(
        campaign_id="c1",
        lead_id="l1",
        destination=Destination(telegram_user_id="123"),
        text="hello",
        idempotency_key="idem-key-1",
        metadata=SendMetadata(sequence_step=0, message_type="cold_touch", campaign_type="cold"),
    )

    first = await service.send_message(request)
    second = await service.send_message(request)

    assert first.result.status == "sent"
    assert second.result.provider_message_id == "msg-1"
    assert len(service.publisher.events) == 1


@pytest.mark.asyncio
async def test_daily_cap_blocks_send():
    settings = Settings(
        BRIDGE_API_KEY="x",
        TELEGRAM_MOCK_MODE=True,
        SESSION_ENCRYPTION_KEY="dGVzdGtleWRHVnpkR3RsZVdSbGN3PT0=",
        N8N_EVENTS_WEBHOOK_URL="http://localhost",
        REDIS_URL="redis://localhost:6379/0",
        DAILY_SEND_CAP=1,
    )
    service = BridgeService(settings)
    fake_storage = FakeStorage()
    fake_storage.daily_sent = 1
    service.storage = fake_storage
    service.publisher = FakePublisher()
    service.telegram_client = FakeTelegramClient()

    request = SendMessageRequest(
        campaign_id="c1",
        lead_id="l1",
        destination=Destination(telegram_user_id="123"),
        text="hello",
        idempotency_key="idem-key-2",
        metadata=SendMetadata(sequence_step=1, message_type="follow_up", campaign_type="cold"),
    )

    response = await service.send_message(request)

    assert response.result.status == "failed"
    assert response.result.error_code == "DAILY_CAP_REACHED"


@pytest.mark.asyncio
async def test_resolve_contact():
    settings = Settings(
        BRIDGE_API_KEY="x",
        TELEGRAM_MOCK_MODE=True,
        SESSION_ENCRYPTION_KEY="dGVzdGtleWRHVnpkR3RsZVdSbGN3PT0=",
        N8N_EVENTS_WEBHOOK_URL="http://localhost",
        REDIS_URL="redis://localhost:6379/0",
    )
    service = BridgeService(settings)
    service.storage = FakeStorage()
    service.publisher = FakePublisher()
    service.telegram_client = FakeTelegramClient()

    response = await service.resolve_contact(
        ResolveContactRequest(campaign_id="c1", lead_id="l1", username="alice")
    )

    assert response.resolved is True
    assert response.username == "@alice"
    assert response.campaign_id == "c1"


def test_schema_serialization_roundtrip():
    now = datetime.now(timezone.utc)
    payload = {
        "campaign_id": "c1",
        "lead_id": "l1",
        "destination": {"telegram_user_id": "100"},
        "text": "hello",
        "idempotency_key": "idem-serial-1",
        "metadata": {"sequence_step": 0, "message_type": "cold_touch", "campaign_type": "cold"},
        "timestamp": now.isoformat(),
    }
    assert payload["campaign_id"] == "c1"
