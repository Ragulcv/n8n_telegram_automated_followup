from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SendStatus(str, Enum):
    SENT = "sent"
    QUEUED = "queued"
    FAILED = "failed"


class EventType(str, Enum):
    INCOMING_MESSAGE = "incoming_message"
    OUTGOING_DELIVERED = "outgoing_delivered"
    OUTGOING_FAILED = "outgoing_failed"
    ACCOUNT_WARNING = "account_warning"


class Destination(BaseModel):
    telegram_user_id: Optional[str] = None
    username: Optional[str] = None


class SendMetadata(BaseModel):
    sequence_step: int = 0
    message_type: str = "cold_touch"
    campaign_type: str = "cold"


class SendMessageRequest(BaseModel):
    campaign_id: str
    lead_id: str
    destination: Destination
    text: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8)
    metadata: SendMetadata


class SendMessageResult(BaseModel):
    status: SendStatus
    provider_message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    error_code: Optional[str] = None


class SendMessageResponse(BaseModel):
    campaign_id: str
    lead_id: str
    idempotency_key: str
    result: SendMessageResult


class SendBatchRequest(BaseModel):
    messages: List[SendMessageRequest] = Field(default_factory=list)


class SendBatchResponse(BaseModel):
    results: List[SendMessageResponse]


class ResolveContactRequest(BaseModel):
    campaign_id: str
    lead_id: str
    telegram_user_id: Optional[str] = None
    username: Optional[str] = None


class ResolveContactResponse(BaseModel):
    campaign_id: str
    lead_id: str
    telegram_user_id: Optional[str] = None
    username: Optional[str] = None
    resolved: bool = False


class AccountHealthResponse(BaseModel):
    status: str
    connected: bool
    daily_sent_count: int
    daily_send_cap: int
    warnings: List[str]


class TelegramEvent(BaseModel):
    event_id: str
    event_type: EventType
    timestamp: datetime
    lead_id: Optional[str] = None
    telegram_user_id: Optional[str] = None
    message_id: Optional[str] = None
    text: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class IncomingMessageSimulation(BaseModel):
    lead_id: Optional[str] = None
    telegram_user_id: Optional[str] = None
    text: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
