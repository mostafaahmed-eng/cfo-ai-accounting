import asyncio
import logging

from app.core.telegram import TelegramClient
from app.services.telegram_bot_config import db_bot_token
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _client_with_token() -> TelegramClient:
    token = await db_bot_token()
    return TelegramClient(token)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def send_telegram_response(
    self, chat_id: int, text: str, reply_markup: dict | None = None
):
    try:
        result = _run_async(_send_message(chat_id, text, reply_markup))
        if not result.get("ok"):
            logger.error("Telegram sendMessage failed: %s", result)
        return result
    except Exception as exc:
        logger.exception("Failed to send Telegram response to %s", chat_id)
        self.retry(exc=exc)


async def _send_message(
    chat_id: int, text: str, reply_markup: dict | None = None
) -> dict:
    client = await _client_with_token()
    return await client.send_message(chat_id, text, reply_markup)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def send_telegram_edit(
    self, chat_id: int, message_id: int, text: str, reply_markup: dict | None = None
):
    try:
        result = _run_async(_edit_message(chat_id, message_id, text, reply_markup))
        if not result.get("ok"):
            logger.error("Telegram editMessageText failed: %s", result)
        return result
    except Exception as exc:
        logger.exception(
            "Failed to edit Telegram message %s in chat %s", message_id, chat_id
        )
        self.retry(exc=exc)


async def _edit_message(
    chat_id: int, message_id: int, text: str, reply_markup: dict | None = None
) -> dict:
    client = await _client_with_token()
    return await client.edit_message_text(chat_id, message_id, text, reply_markup)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def answer_telegram_callback(
    self, callback_query_id: str, text: str | None = None, show_alert: bool = False
):
    try:
        result = _run_async(_answer_callback(callback_query_id, text, show_alert))
        if not result.get("ok"):
            logger.error("Telegram answerCallbackQuery failed: %s", result)
        return result
    except Exception as exc:
        logger.exception("Failed to answer Telegram callback %s", callback_query_id)
        self.retry(exc=exc)


async def _answer_callback(
    callback_query_id: str, text: str | None = None, show_alert: bool = False
) -> dict:
    client = await _client_with_token()
    return await client.answer_callback_query(callback_query_id, text, show_alert)
