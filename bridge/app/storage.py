import json
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis


class Storage:
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        await self._redis.ping()

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()

    @property
    def client(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("Redis client is not initialized")
        return self._redis

    @staticmethod
    def _daily_key(account_key: str) -> str:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"bridge:daily-sent:{account_key}:{day}"

    async def increment_daily_sent(self, account_key: str) -> int:
        key = self._daily_key(account_key)
        value = await self.client.incr(key)
        if value == 1:
            await self.client.expire(key, 60 * 60 * 24 * 3)
        return int(value)

    async def get_daily_sent(self, account_key: str) -> int:
        value = await self.client.get(self._daily_key(account_key))
        return int(value) if value is not None else 0

    async def get_idempotency(self, key: str) -> Optional[dict[str, Any]]:
        value = await self.client.get(f"bridge:idempotency:{key}")
        if value is None:
            return None
        return json.loads(value)

    async def set_idempotency(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        await self.client.set(
            f"bridge:idempotency:{key}",
            json.dumps(payload, default=str),
            ex=ttl_seconds,
        )

    async def get_encrypted_session(self) -> Optional[str]:
        return await self.client.get("bridge:telegram:session")

    async def set_encrypted_session(self, encrypted_session: str) -> None:
        await self.client.set("bridge:telegram:session", encrypted_session)

    async def set_last_error(self, message: str) -> None:
        await self.client.set("bridge:last-error", message, ex=60 * 60 * 24)

    async def get_last_error(self) -> Optional[str]:
        return await self.client.get("bridge:last-error")
