import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException

from app.config import Settings, get_settings
from app.schemas import (
    AccountHealthResponse,
    ErrorResponse,
    IncomingMessageSimulation,
    ResolveContactRequest,
    ResolveContactResponse,
    SendBatchRequest,
    SendBatchResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.security import require_api_key
from app.service import BridgeService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.bridge_log_level.upper(), logging.INFO))

    service = BridgeService(settings)
    await service.startup()
    app.state.service = service

    try:
        yield
    finally:
        await service.shutdown()


app = FastAPI(
    title="Telegram Outreach Bridge",
    version="1.0.0",
    lifespan=lifespan,
)


def get_service() -> BridgeService:
    service = getattr(app.state, "service", None)
    if service is None:
        raise RuntimeError("Bridge service is not initialized")
    return service


@app.get("/health")
async def healthcheck() -> dict:
    return {"ok": True}


@app.get(
    "/v1/account/health",
    response_model=AccountHealthResponse,
    responses={401: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
async def get_account_health(service: BridgeService = Depends(get_service)) -> AccountHealthResponse:
    return await service.get_account_health()


@app.post(
    "/v1/contacts/resolve",
    response_model=ResolveContactResponse,
    responses={401: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
async def resolve_contact(
    request: ResolveContactRequest,
    service: BridgeService = Depends(get_service),
) -> ResolveContactResponse:
    return await service.resolve_contact(request)


@app.post(
    "/v1/messages/send",
    response_model=SendMessageResponse,
    responses={401: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
async def send_message(
    request: SendMessageRequest,
    service: BridgeService = Depends(get_service),
) -> SendMessageResponse:
    return await service.send_message(request)


@app.post(
    "/v1/messages/send-batch",
    response_model=SendBatchResponse,
    responses={401: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
async def send_batch(
    request: SendBatchRequest,
    service: BridgeService = Depends(get_service),
) -> SendBatchResponse:
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    return await service.send_batch(request)


@app.post(
    "/v1/simulate/incoming",
    response_model=dict,
    responses={401: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
async def simulate_incoming(
    request: IncomingMessageSimulation,
    service: BridgeService = Depends(get_service),
) -> dict:
    await service.simulate_incoming(request.telegram_user_id, request.text, request.lead_id)
    return {"ok": True}


@app.get("/v1/config", dependencies=[Depends(require_api_key)])
async def show_runtime_config(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "mock_mode": settings.telegram_mock_mode,
        "daily_send_cap": settings.daily_send_cap,
        "webhook_url": settings.n8n_events_webhook_url,
    }
