import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schemas import TelegramEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, target_url: str):
        self._target_url = target_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def publish(self, event: TelegramEvent) -> None:
        if not self._target_url:
            logger.warning("N8N_EVENTS_WEBHOOK_URL is empty; skipping event publish")
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self._target_url, json=event.model_dump(mode="json"))
            response.raise_for_status()
