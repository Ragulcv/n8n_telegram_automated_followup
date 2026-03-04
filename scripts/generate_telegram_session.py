#!/usr/bin/env python3
import asyncio

from telethon import TelegramClient
from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError


async def request_code(client: TelegramClient, phone: str, force_sms: bool = False):
    # Telethon signatures can vary by version; keep fallback for compatibility.
    try:
        return await client.send_code_request(phone, force_sms=force_sms)
    except TypeError:
        return await client.send_code_request(phone)


async def main() -> None:
    api_id = int(input("TELEGRAM_API_ID: ").strip())
    api_hash = input("TELEGRAM_API_HASH: ").strip()
    phone = input("TELEGRAM_PHONE (international format): ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await request_code(client, phone)
        print("\nCheck your Telegram app first (official 'Telegram' chat / 777000).")
        print("Tip: each new resend invalidates the previous code.")
        for attempt in range(1, 6):
            code = input("Telegram login code (or type 'resend' / 'sms'): ").strip().replace(" ", "")
            lower = code.lower()
            if lower in {"resend", "r"}:
                await request_code(client, phone)
                print("[INFO] Requested a fresh code.")
                continue
            if lower in {"sms", "force_sms"}:
                await request_code(client, phone, force_sms=True)
                print("[INFO] Requested SMS code (if Telegram allows SMS fallback).")
                continue
            try:
                await client.sign_in(phone=phone, code=code)
                break
            except SessionPasswordNeededError:
                password = input("Two-step password (if enabled): ").strip()
                await client.sign_in(password=password)
                break
            except PhoneCodeInvalidError:
                print(f"[WARN] Invalid code. Try again ({attempt}/5).")
                if attempt == 5:
                    raise
            except PhoneCodeExpiredError:
                print("[WARN] Code expired. Requesting a new code...")
                await client.send_code_request(phone)
                if attempt == 5:
                    raise

    session = client.session.save()
    print("\nTELEGRAM_SESSION_STRING=")
    print(session)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
