#!/usr/bin/env python3
import asyncio

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberFloodError,
    SendCodeUnavailableError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession


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


def print_ascii_qr(url: str) -> None:
    try:
        import qrcode  # type: ignore

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        print("")
        for row in matrix:
            print("".join("██" if cell else "  " for cell in row))
        print("")
    except Exception:
        print("[INFO] Could not render QR in terminal (optional dependency missing).")
        print("[INFO] Install once with: pip3 install qrcode")

    print(f"[INFO] QR login URL: {url}")


async def sign_in_with_qr(client: TelegramClient) -> bool:
    print("\nStarting QR login flow...")
    print("1) Open Telegram mobile app where this account is already logged in.")
    print("2) Go to Settings -> Devices -> Link Desktop Device.")
    print("3) Scan the QR shown below within ~2 minutes.")
    qr_login = await client.qr_login()
    print_ascii_qr(qr_login.url)

    try:
        await qr_login.wait(timeout=120)
    except asyncio.TimeoutError:
        print("[WARN] QR login timed out. Run the script again and retry scan.")
        return False
    except SessionPasswordNeededError:
        password = input("Two-step password (if enabled): ").strip()
        await client.sign_in(password=password)

    if not await client.is_user_authorized():
        print("[WARN] QR scan did not complete authorization.")
        return False
    return True


async def main() -> None:
    api_id = int(input("TELEGRAM_API_ID: ").strip())
    api_hash = input("TELEGRAM_API_HASH: ").strip()
    phone = input("TELEGRAM_PHONE (international format): ").strip()
    login_method = input("Login method [otp/qr] (default otp): ").strip().lower() or "otp"

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        if login_method in {"qr", "q"}:
            if not await sign_in_with_qr(client):
                await client.disconnect()
                return
        else:
            if not await request_code(client, phone):
                use_qr_fallback = input("OTP unavailable. Try QR login instead? [y/N]: ").strip().lower()
                if use_qr_fallback in {"y", "yes"}:
                    if not await sign_in_with_qr(client):
                        await client.disconnect()
                        return
                else:
                    await client.disconnect()
                    return
            else:
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
