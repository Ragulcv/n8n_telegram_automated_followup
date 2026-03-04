#!/usr/bin/env python3
import asyncio

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberFloodError,
    SendCodeUnavailableError,
)
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError


async def request_code(client: TelegramClient, phone: str, force_sms: bool = False):
    # Telethon signatures can vary by version; keep fallback for compatibility.
    try:
        await client.send_code_request(phone, force_sms=force_sms)
        return True
    except TypeError:
        try:
            await client.send_code_request(phone)
            return True
        except (SendCodeUnavailableError, FloodWaitError, PhoneNumberFloodError):
            pass
    except (SendCodeUnavailableError, FloodWaitError, PhoneNumberFloodError):
        pass

    try:
        # A second attempt without force_sms sometimes works across Telethon versions.
        await client.send_code_request(phone)
        return True
    except FloodWaitError as exc:
        wait_seconds = int(getattr(exc, "seconds", 60))
        print(f"[WARN] Telegram rate-limited code requests. Wait {wait_seconds}s before retry.")
        return False
    except SendCodeUnavailableError:
        print("[WARN] Telegram temporarily exhausted available OTP delivery methods for this number.")
        print("[INFO] Wait 10-15 minutes, then run script again and request code only once.")
        return False
    except PhoneNumberFloodError:
        print("[WARN] Too many login attempts for this number. Telegram imposed a temporary lock.")
        print("[INFO] Wait longer (often hours) before retrying.")
        return False


async def main() -> None:
    api_id = int(input("TELEGRAM_API_ID: ").strip())
    api_hash = input("TELEGRAM_API_HASH: ").strip()
    phone = input("TELEGRAM_PHONE (international format): ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        if not await request_code(client, phone):
            await client.disconnect()
            return
        print("\nCheck your Telegram app first (official 'Telegram' chat / 777000).")
        print("Tip: each new resend invalidates the previous code.")
        code_attempts = 0
        while code_attempts < 5:
            code = input("Telegram login code (or type 'resend' / 'sms'): ").strip().replace(" ", "")
            lower = code.lower()
            if lower in {"resend", "r"}:
                if await request_code(client, phone):
                    print("[INFO] Requested a fresh code.")
                continue
            if lower in {"sms", "force_sms"}:
                if await request_code(client, phone, force_sms=True):
                    print("[INFO] Requested SMS code (if Telegram allows SMS fallback).")
                continue
            code_attempts += 1
            try:
                await client.sign_in(phone=phone, code=code)
                break
            except SessionPasswordNeededError:
                password = input("Two-step password (if enabled): ").strip()
                await client.sign_in(password=password)
                break
            except PhoneCodeInvalidError:
                print(f"[WARN] Invalid code. Try again ({code_attempts}/5).")
                if code_attempts == 5:
                    raise
            except PhoneCodeExpiredError:
                print("[WARN] Code expired. Requesting a new code...")
                if not await request_code(client, phone):
                    await client.disconnect()
                    return
                if code_attempts == 5:
                    raise

    session = client.session.save()
    print("\nTELEGRAM_SESSION_STRING=")
    print(session)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
