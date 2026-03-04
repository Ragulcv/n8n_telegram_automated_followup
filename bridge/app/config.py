from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bridge_env: str = Field(default="dev", alias="BRIDGE_ENV")
    bridge_host: str = Field(default="0.0.0.0", alias="BRIDGE_HOST")
    bridge_port: int = Field(default=8080, alias="BRIDGE_PORT")
    bridge_log_level: str = Field(default="INFO", alias="BRIDGE_LOG_LEVEL")
    bridge_api_key: str = Field(default="", alias="BRIDGE_API_KEY")

    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    telegram_api_id: int = Field(default=0, alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(default="", alias="TELEGRAM_API_HASH")
    telegram_phone: str = Field(default="", alias="TELEGRAM_PHONE")
    telegram_session_string: str = Field(default="", alias="TELEGRAM_SESSION_STRING")
    telegram_mock_mode: bool = Field(default=True, alias="TELEGRAM_MOCK_MODE")

    session_encryption_key: str = Field(default="", alias="SESSION_ENCRYPTION_KEY")

    n8n_events_webhook_url: str = Field(default="", alias="N8N_EVENTS_WEBHOOK_URL")

    ops_bot_token: str = Field(default="", alias="OPS_BOT_TOKEN")
    ops_chat_id: str = Field(default="", alias="OPS_CHAT_ID")

    daily_send_cap: int = Field(default=25, alias="DAILY_SEND_CAP")
    idempotency_ttl_seconds: int = Field(default=604800, alias="IDEMPOTENCY_TTL_SECONDS")
    delivery_retry_delays: str = Field(default="120,600,1800", alias="DELIVERY_RETRY_DELAYS")

    @property
    def retry_delay_seconds(self) -> List[int]:
        values: List[int] = []
        for item in self.delivery_retry_delays.split(","):
            item = item.strip()
            if not item:
                continue
            values.append(int(item))
        return values or [120, 600, 1800]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
