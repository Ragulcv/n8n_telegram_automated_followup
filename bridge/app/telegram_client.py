import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from uuid import uuid4

from app.config import Settings
from app.schemas import EventType, TelegramEvent

logger = logging.getLogger(__name__)


class TelegramClientError(Exception):
    """Raised for Telegram client-level errors."""


class TelegramRateLimitError(TelegramClientError):
    """Raised when Telegram responds with flood/rate limiting."""


IncomingHandler = Callable[[TelegramEvent], Awaitable[None]]


@dataclass
class ResolveResult:
    telegram_user_id: Optional[str]
    username: Optional[str]
    resolved: bool


class BaseTelegramClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._incoming_handler: Optional[IncomingHandler] = None

    async def connect(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def send_message(self, telegram_user_id: Optional[str], username: Optional[str], text: str) -> str:
        raise NotImplementedError

    async def resolve_contact(self, telegram_user_id: Optional[str], username: Optional[str]) -> ResolveResult:
        raise NotImplementedError

    def set_incoming_handler(self, handler: IncomingHandler) -> None:
        self._incoming_handler = handler

    async def emit_incoming(self, telegram_user_id: Optional[str], text: str) -> None:
        if self._incoming_handler is None:
            return
        event = TelegramEvent(
            event_id=str(uuid4()),
            event_type=EventType.INCOMING_MESSAGE,
            timestamp=datetime.now(timezone.utc),
            telegram_user_id=telegram_user_id,
            text=text,
            raw={"source": "bridge"},
        )
        await self._incoming_handler(event)

    @property
    def connected(self) -> bool:
        raise NotImplementedError


class MockTelegramClient(BaseTelegramClient):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        logger.info("MockTelegramClient connected")

    async def close(self) -> None:
        self._connected = False

    async def send_message(self, telegram_user_id: Optional[str], username: Optional[str], text: str) -> str:
        if not self._connected:
            raise TelegramClientError("Mock Telegram client is not connected")
        _ = telegram_user_id, username, text
        return f"mock-{uuid4()}"

    async def resolve_contact(self, telegram_user_id: Optional[str], username: Optional[str]) -> ResolveResult:
        if telegram_user_id:
            return ResolveResult(telegram_user_id=telegram_user_id, username=username, resolved=True)
        if username:
            normalized = username if username.startswith("@") else f"@{username}"
            return ResolveResult(telegram_user_id=None, username=normalized, resolved=True)
        return ResolveResult(telegram_user_id=None, username=None, resolved=False)

    @property
    def connected(self) -> bool:
        return self._connected


class TelethonTelegramClient(BaseTelegramClient):
    def __init__(self, settings: Settings, decrypted_session: str):
        super().__init__(settings)
        self._decrypted_session = decrypted_session
        self._connected = False
        self._client = None

    async def connect(self) -> None:
        try:
            from telethon import TelegramClient, events
            from telethon.errors import FloodWaitError
            from telethon.sessions import StringSession
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise TelegramClientError("Telethon is not installed") from exc

        if not self.settings.telegram_api_id or not self.settings.telegram_api_hash:
            raise TelegramClientError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

        self._client = TelegramClient(
            StringSession(self._decrypted_session),
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        )

        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise TelegramClientError(
                "Telegram session is not authorized. Generate a valid StringSession and set TELEGRAM_SESSION_STRING."
            )

        @self._client.on(events.NewMessage(incoming=True))
        async def _handler(event):
            if self._incoming_handler is None:
                return
            sender = await event.get_sender()
            telegram_user_id = str(getattr(sender, "id", "")) if sender else None
            payload = TelegramEvent(
                event_id=str(uuid4()),
                event_type=EventType.INCOMING_MESSAGE,
                timestamp=datetime.now(timezone.utc),
                telegram_user_id=telegram_user_id,
                message_id=str(getattr(event.message, "id", "")),
                text=getattr(event.message, "message", "") or "",
                raw={"source": "telegram", "peer_id": str(getattr(event.message, "peer_id", ""))},
            )
            await self._incoming_handler(payload)

        self._flood_wait_error = FloodWaitError
        self._connected = True
        logger.info("TelethonTelegramClient connected")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
        self._connected = False

    async def send_message(self, telegram_user_id: Optional[str], username: Optional[str], text: str) -> str:
        if not self._connected or self._client is None:
            raise TelegramClientError("Telegram client is not connected")

        try:
            destination = self._resolve_destination(telegram_user_id, username)
            message = await self._client.send_message(destination, text)
            return str(message.id)
        except self._flood_wait_error as exc:  # type: ignore[attr-defined]
            raise TelegramRateLimitError(f"FLOOD_WAIT_{exc.seconds}") from exc
        except Exception as exc:  # pragma: no cover - depends on external service
            raise TelegramClientError(str(exc)) from exc

    async def resolve_contact(self, telegram_user_id: Optional[str], username: Optional[str]) -> ResolveResult:
        if not self._connected or self._client is None:
            raise TelegramClientError("Telegram client is not connected")

        try:
            destination = self._resolve_destination(telegram_user_id, username)
            entity = await self._client.get_entity(destination)
            resolved_id = str(getattr(entity, "id", "")) or None
            resolved_username = getattr(entity, "username", None)
            if resolved_username and not str(resolved_username).startswith("@"):
                resolved_username = f"@{resolved_username}"
            return ResolveResult(
                telegram_user_id=resolved_id,
                username=resolved_username,
                resolved=resolved_id is not None or resolved_username is not None,
            )
        except Exception:
            return ResolveResult(telegram_user_id=None, username=None, resolved=False)

    def _resolve_destination(self, telegram_user_id: Optional[str], username: Optional[str]):
        if telegram_user_id:
            try:
                return int(telegram_user_id)
            except ValueError as exc:
                raise TelegramClientError("telegram_user_id must be numeric") from exc
        if username:
            return username if username.startswith("@") else f"@{username}"
        raise TelegramClientError("Either telegram_user_id or username is required")

    @property
    def connected(self) -> bool:
        return self._connected
