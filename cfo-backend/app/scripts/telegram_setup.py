"""One-command Telegram webhook setup.

Reads TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET and PUBLIC_BASE_URL from the
environment, calls setWebhook, then verifies with getWebhookInfo.

Run from the backend container or any machine that has the bot token:
    python -m app.scripts.telegram_setup
"""

import asyncio
import os
import sys

import httpx

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


async def _call(token: str, method: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{TELEGRAM_API_BASE}{token}/{method}", json=payload
        )
        response.raise_for_status()
        return response.json()


async def _main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

    errors = []
    if not token:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    if not secret:
        errors.append("TELEGRAM_WEBHOOK_SECRET is not set")
    if not public_base_url:
        errors.append("PUBLIC_BASE_URL is not set")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print("\nUsage:")
        print("  TELEGRAM_BOT_TOKEN=<token> \\")
        print("  TELEGRAM_WEBHOOK_SECRET=<secret> \\")
        print("  PUBLIC_BASE_URL=https://yourdomain.com \\")
        print("  python -m app.scripts.telegram_setup")
        return 1

    webhook_url = f"{public_base_url}/api/v1/telegram/webhook"
    print(f"Webhook URL: {webhook_url}")

    try:
        result = await _call(
            token,
            "setWebhook",
            {
                "url": webhook_url,
                "secret_token": secret,
                "allowed_updates": ["message", "callback_query"],
            },
        )
    except httpx.HTTPError as exc:
        print(f"[FAIL] setWebhook request failed: {exc}")
        return 1

    if not result.get("ok"):
        print(f"[FAIL] setWebhook returned an error: {result}")
        return 1

    print(f"[OK] setWebhook: {result.get('result')}")

    try:
        info = await _call(token, "getWebhookInfo", {})
    except httpx.HTTPError as exc:
        print(f"[FAIL] getWebhookInfo request failed: {exc}")
        return 1

    if not info.get("ok"):
        print(f"[FAIL] getWebhookInfo returned an error: {info}")
        return 1

    webhook_info = info.get("result", {})
    configured_url = webhook_info.get("url", "")
    print(f"[OK] getWebhookInfo url: {configured_url}")

    success = configured_url == webhook_url
    if not success:
        print(
            f"[FAIL] Telegram reports a different webhook URL "
            f"({configured_url!r} != {webhook_url!r})"
        )
        return 1

    last_error = webhook_info.get("last_error_message")
    if last_error:
        print(f"[WARN] Telegram reports a last_error_message: {last_error}")

    pending = webhook_info.get("pending_update_count", 0)
    print(f"[INFO] pending_update_count: {pending}")
    print("\nWebhook configured successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
