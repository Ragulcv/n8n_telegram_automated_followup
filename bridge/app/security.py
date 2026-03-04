from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Header, HTTPException, status
from typing import Optional

from app.config import Settings, get_settings


def build_fernet(settings: Settings) -> Fernet:
    if not settings.session_encryption_key:
        raise RuntimeError("SESSION_ENCRYPTION_KEY is required")
    return Fernet(settings.session_encryption_key.encode("utf-8"))


def encrypt_session(raw_session: str, settings: Settings) -> str:
    fernet = build_fernet(settings)
    encrypted = fernet.encrypt(raw_session.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_session(encrypted_session: str, settings: Settings) -> str:
    fernet = build_fernet(settings)
    try:
        decrypted = fernet.decrypt(encrypted_session.encode("utf-8"))
    except InvalidToken as exc:
        raise RuntimeError("Stored Telegram session cannot be decrypted") from exc
    return decrypted.decode("utf-8")


def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.bridge_api_key and x_api_key == settings.bridge_api_key:
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
