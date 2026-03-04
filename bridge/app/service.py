import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from app.config import Settings
from app.events import EventPublisher
from app.schemas import (
    AccountHealthResponse,
    EventType,
    ResolveContactRequest,
    ResolveContactResponse,
    SendBatchRequest,
    SendBatchResponse,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageResult,
    SendStatus,
    TelegramEvent,
)
from app.security import decrypt_session, encrypt_session
from app.storage import Storage
from app.telegram_client import (
    BaseTelegramClient,
    MockTelegramClient,
    TelethonTelegramClient,
    TelegramClientError,
    TelegramRateLimitError,
)

logger = logging.getLogger(__name__)


class BridgeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.redis_url)
        self.publisher = EventPublisher(settings.n8n_events_webhook_url)
        self.telegram_client: BaseTelegramClient

    @property
    def _account_key(self) -> str:
        return self.settings.telegram_phone or "default"

    async def startup(self) -> None:
        await self.storage.connect()

        if self.settings.telegram_mock_mode:
            self.telegram_client = MockTelegramClient(self.settings)
        else:
            decrypted = await self._load_or_seed_session()
            self.telegram_client = TelethonTelegramClient(self.settings, decrypted)

        self.telegram_client.set_incoming_handler(self._handle_incoming_event)
        await self.telegram_client.connect()

    async def shutdown(self) -> None:
        if hasattr(self, "telegram_client"):
            await self.telegram_client.close()
        await self.storage.close()

    async def _load_or_seed_session(self) -> str:
        encrypted = await self.storage.get_encrypted_session()

        if encrypted:
            return decrypt_session(encrypted, self.settings)

        if not self.settings.telegram_session_string:
            raise RuntimeError(
                "No encrypted session in storage and TELEGRAM_SESSION_STRING is empty. "
                "Set TELEGRAM_SESSION_STRING once, then restart."
            )

        encrypted = encrypt_session(self.settings.telegram_session_string, self.settings)
        await self.storage.set_encrypted_session(encrypted)
        return self.settings.telegram_session_string

    async def get_account_health(self) -> AccountHealthResponse:
        warnings: List[str] = []
        daily_sent = await self.storage.get_daily_sent(self._account_key)
        if daily_sent >= self.settings.daily_send_cap:
            warnings.append("DAILY_CAP_REACHED")
        last_error = await self.storage.get_last_error()
        if last_error:
            warnings.append(last_error)

        status = "healthy" if self.telegram_client.connected and not warnings else "degraded"
        return AccountHealthResponse(
            status=status,
            connected=self.telegram_client.connected,
            daily_sent_count=daily_sent,
            daily_send_cap=self.settings.daily_send_cap,
            warnings=warnings,
        )

    async def resolve_contact(self, request: ResolveContactRequest) -> ResolveContactResponse:
        result = await self.telegram_client.resolve_contact(request.telegram_user_id, request.username)
        return ResolveContactResponse(
            campaign_id=request.campaign_id,
            lead_id=request.lead_id,
            telegram_user_id=result.telegram_user_id,
            username=result.username,
            resolved=result.resolved,
        )

    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        cached = await self.storage.get_idempotency(request.idempotency_key)
        if cached:
            return SendMessageResponse.model_validate(cached)

        daily_sent = await self.storage.get_daily_sent(self._account_key)
        if daily_sent >= self.settings.daily_send_cap:
            response = SendMessageResponse(
                campaign_id=request.campaign_id,
                lead_id=request.lead_id,
                idempotency_key=request.idempotency_key,
                result=SendMessageResult(
                    status=SendStatus.FAILED,
                    error_code="DAILY_CAP_REACHED",
                ),
            )
            await self._publish_event(
                event_type=EventType.ACCOUNT_WARNING,
                lead_id=request.lead_id,
                telegram_user_id=request.destination.telegram_user_id,
                text="Daily cap reached",
                raw={"campaign_id": request.campaign_id, "idempotency_key": request.idempotency_key},
            )
            await self.storage.set_idempotency(
                request.idempotency_key,
                response.model_dump(mode="json"),
                self.settings.idempotency_ttl_seconds,
            )
            return response

        try:
            provider_message_id = await self.telegram_client.send_message(
                request.destination.telegram_user_id,
                request.destination.username,
                request.text,
            )
            await self.storage.increment_daily_sent(self._account_key)
            response = SendMessageResponse(
                campaign_id=request.campaign_id,
                lead_id=request.lead_id,
                idempotency_key=request.idempotency_key,
                result=SendMessageResult(
                    status=SendStatus.SENT,
                    provider_message_id=provider_message_id,
                    sent_at=datetime.now(timezone.utc),
                ),
            )
            await self._publish_event(
                event_type=EventType.OUTGOING_DELIVERED,
                lead_id=request.lead_id,
                telegram_user_id=request.destination.telegram_user_id,
                message_id=provider_message_id,
                raw={
                    "campaign_id": request.campaign_id,
                    "metadata": request.metadata.model_dump(mode="json"),
                    "idempotency_key": request.idempotency_key,
                },
            )
            await self.storage.set_idempotency(
                request.idempotency_key,
                response.model_dump(mode="json"),
                self.settings.idempotency_ttl_seconds,
            )
            return response
        except TelegramRateLimitError as exc:
            await self.storage.set_last_error(str(exc))
            response = SendMessageResponse(
                campaign_id=request.campaign_id,
                lead_id=request.lead_id,
                idempotency_key=request.idempotency_key,
                result=SendMessageResult(
                    status=SendStatus.FAILED,
                    error_code="RATE_LIMIT",
                ),
            )
            await self._publish_event(
                event_type=EventType.ACCOUNT_WARNING,
                lead_id=request.lead_id,
                telegram_user_id=request.destination.telegram_user_id,
                text=str(exc),
                raw={"campaign_id": request.campaign_id},
            )
            await self.storage.set_idempotency(
                request.idempotency_key,
                response.model_dump(mode="json"),
                self.settings.idempotency_ttl_seconds,
            )
            return response
        except TelegramClientError as exc:
            await self.storage.set_last_error(str(exc))
            response = SendMessageResponse(
                campaign_id=request.campaign_id,
                lead_id=request.lead_id,
                idempotency_key=request.idempotency_key,
                result=SendMessageResult(
                    status=SendStatus.FAILED,
                    error_code="SEND_FAILED",
                ),
            )
            await self._publish_event(
                event_type=EventType.OUTGOING_FAILED,
                lead_id=request.lead_id,
                telegram_user_id=request.destination.telegram_user_id,
                text=str(exc),
                raw={"campaign_id": request.campaign_id},
            )
            await self.storage.set_idempotency(
                request.idempotency_key,
                response.model_dump(mode="json"),
                self.settings.idempotency_ttl_seconds,
            )
            return response

    async def send_batch(self, request: SendBatchRequest) -> SendBatchResponse:
        results: List[SendMessageResponse] = []
        for message in request.messages:
            results.append(await self.send_message(message))
        return SendBatchResponse(results=results)

    async def simulate_incoming(self, telegram_user_id: Optional[str], text: str, lead_id: Optional[str]) -> None:
        event = TelegramEvent(
            event_id=str(uuid4()),
            event_type=EventType.INCOMING_MESSAGE,
            timestamp=datetime.now(timezone.utc),
            lead_id=lead_id,
            telegram_user_id=telegram_user_id,
            text=text,
            raw={"source": "simulation"},
        )
        try:
            await self.publisher.publish(event)
        except Exception as exc:
            logger.warning("Simulated inbound event could not be delivered to n8n: %s", exc)

    async def _handle_incoming_event(self, event: TelegramEvent) -> None:
        await self.publisher.publish(event)

    async def _publish_event(
        self,
        event_type: EventType,
        lead_id: Optional[str],
        telegram_user_id: Optional[str],
        text: Optional[str] = None,
        message_id: Optional[str] = None,
        raw: Optional[Dict] = None,
    ) -> None:
        event = TelegramEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            lead_id=lead_id,
            telegram_user_id=telegram_user_id,
            message_id=message_id,
            text=text,
            raw=raw or {},
        )
        try:
            await self.publisher.publish(event)
        except Exception as exc:  # pragma: no cover - network error
            logger.warning("Failed to publish event: %s", exc)
