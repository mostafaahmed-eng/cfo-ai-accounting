"""Long-polling Telegram update worker.

Telegram webhooks require a public HTTPS endpoint that Telegram can reach. When
that is unavailable, this worker polls the Bot API with getUpdates and forwards
each update to the local webhook endpoint so the existing webhook logic
(pairing, extraction, drafts, callbacks) is reused unchanged.

Run from the backend image:
    python -m app.services.telegram_polling
"""

import asyncio
import logging
import sys

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"
GET_UPDATES_TIMEOUT_SECONDS = 25
# The local webhook is rate limited (RATE_LIMIT_WEBHOOK, 30/minute), so pace
# deliveries to stay safely under the limit.
DELIVERY_MIN_INTERVAL_SECONDS = 2.2
RETRY_BACKOFF_SECONDS = 30
RATE_LIMIT_BACKOFF_SECONDS = 60
CONFLICT_BACKOFF_SECONDS = 60


def load_offset(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            return int(handle.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def save_offset(path: str, offset: int) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(offset))
    except OSError:
        logger.warning("Could not persist polling offset to %s", path)


async def fetch_updates(client: httpx.AsyncClient, token: str, offset: int) -> dict:
    response = await client.get(
        f"{TELEGRAM_API_BASE}{token}/getUpdates",
        params={
            "timeout": GET_UPDATES_TIMEOUT_SECONDS,
            "offset": offset,
            "allowed_updates": '["message", "callback_query"]',
        },
    )
    response.raise_for_status()
    return response.json()


async def deliver_update(
    client: httpx.AsyncClient,
    update: dict,
    *,
    webhook_url: str,
    secret: str,
) -> int:
    response = await client.post(
        webhook_url,
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
    )
    return response.status_code


async def deliver_update_with_retry(
    client: httpx.AsyncClient,
    update: dict,
    *,
    webhook_url: str,
    secret: str,
) -> None:
    while True:
        status_code = await deliver_update(
            client, update, webhook_url=webhook_url, secret=secret
        )
        if 200 <= status_code < 300:
            return
        if status_code == 429:
            logger.warning(
                "Local webhook rate limited (HTTP 429); retrying update %s in %ss",
                update.get("update_id"),
                RATE_LIMIT_BACKOFF_SECONDS,
            )
            await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            continue
        logger.warning(
            "Local webhook returned HTTP %s for update %s; retrying in %ss",
            status_code,
            update.get("update_id"),
            RETRY_BACKOFF_SECONDS,
        )
        await asyncio.sleep(RETRY_BACKOFF_SECONDS)


async def run(
    *,
    settings=None,
    client: httpx.AsyncClient | None = None,
    offset_path: str | None = None,
    max_cycles: int | None = None,
) -> int:
    settings = settings or get_settings()
    token = settings.TELEGRAM_BOT_TOKEN
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    webhook_url = settings.TELEGRAM_POLLING_INTERNAL_WEBHOOK_URL

    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not secret:
        missing.append("TELEGRAM_WEBHOOK_SECRET")
    if not webhook_url:
        missing.append("TELEGRAM_POLLING_INTERNAL_WEBHOOK_URL")
    if missing:
        logger.error(
            "Polling worker is missing required config: %s", ", ".join(missing)
        )
        return 1

    offset_path = offset_path or settings.TELEGRAM_POLLING_OFFSET_FILE
    offset = load_offset(offset_path)
    logger.info("Telegram polling started (offset=%s, webhook=%s)", offset, webhook_url)

    if client is not None:
        return await _run_loop(
            http=client,
            token=token,
            secret=secret,
            webhook_url=webhook_url,
            offset_path=offset_path,
            offset=offset,
            max_cycles=max_cycles,
        )

    async with httpx.AsyncClient(timeout=40.0) as http:
        return await _run_loop(
            http=http,
            token=token,
            secret=secret,
            webhook_url=webhook_url,
            offset_path=offset_path,
            offset=offset,
            max_cycles=max_cycles,
        )


async def _run_loop(
    *,
    http: httpx.AsyncClient,
    token: str,
    secret: str,
    webhook_url: str,
    offset_path: str,
    offset: int,
    max_cycles: int | None,
) -> int:
    conflict_reported = False
    cycles = 0
    while True:
        cycles += 1
        if max_cycles is not None and cycles > max_cycles:
            return 0

        try:
            result = await fetch_updates(http, token, offset)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 409:
                if not conflict_reported:
                    token_hint = f"{token[:6]}...{token[-4:]}"
                    logger.error(
                        "Telegram reports a webhook is configured for this bot. "
                        "getUpdates requires a webhook to be removed first. "
                        "Run deleteWebhook for bot %s or disable polling.",
                        token_hint,
                    )
                    conflict_reported = True
                await asyncio.sleep(CONFLICT_BACKOFF_SECONDS)
                continue
            if status_code in (401, 404):
                logger.error(
                    "Telegram getUpdates failed (HTTP %s). Check TELEGRAM_BOT_TOKEN.",
                    status_code,
                )
                return 1
            logger.warning(
                "Telegram getUpdates failed (HTTP %s); retrying in %ss",
                status_code,
                RETRY_BACKOFF_SECONDS,
            )
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)
            continue
        except httpx.HTTPError as exc:
            logger.warning(
                "Telegram getUpdates request failed (%s); retrying in %ss",
                exc,
                RETRY_BACKOFF_SECONDS,
            )
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)
            continue

        conflict_reported = False
        if not result.get("ok"):
            logger.error(
                "Telegram getUpdates returned ok=false (%s); retrying in %ss",
                result,
                RETRY_BACKOFF_SECONDS,
            )
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)
            continue

        updates = result.get("result", [])
        for update in updates:
            await deliver_update_with_retry(
                http, update, webhook_url=webhook_url, secret=secret
            )
            await asyncio.sleep(DELIVERY_MIN_INTERVAL_SECONDS)

        if updates:
            new_offset = max(
                offset, max(int(update.get("update_id", 0)) for update in updates) + 1
            )
            if new_offset > offset:
                offset = new_offset
                save_offset(offset_path, offset)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Polling worker stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
