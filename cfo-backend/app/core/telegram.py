import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TELEGRAM_API_BASE = "https://api.telegram.org/bot"
TELEGRAM_FILE_BASE = "https://api.telegram.org/file/bot"


class TelegramFileError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str | None = None):
        self._token = token or settings.TELEGRAM_BOT_TOKEN
        self._base_url = f"{TELEGRAM_API_BASE}{self._token}"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        payload: dict = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return await self._request("sendMessage", payload)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self._request("editMessageText", payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict:
        payload: dict = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text
        return await self._request("answerCallbackQuery", payload)

    async def download_file(self, file_id: str, token: str | None = None) -> bytes:
        if token:
            base_url = f"{TELEGRAM_API_BASE}{token}"
            file_base_url = f"{TELEGRAM_FILE_BASE}{token}"
        else:
            base_url = self._base_url
            file_base_url = f"{TELEGRAM_FILE_BASE}{self._token}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            metadata_response = await client.post(
                f"{base_url}/getFile",
                json={"file_id": file_id},
            )
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            file_path = metadata.get("result", {}).get("file_path")
            if not metadata.get("ok") or not file_path:
                raise TelegramFileError("Telegram did not return a downloadable file")

            file_response = await client.get(f"{file_base_url}/{file_path}")
            file_response.raise_for_status()
            return file_response.content

    async def _request(self, method: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/{method}",
                json=payload,
            )
            result = response.json()
            if not result.get("ok"):
                logger.error("Telegram API %s failed: %s", method, result)
            return result


telegram_client = TelegramClient()
