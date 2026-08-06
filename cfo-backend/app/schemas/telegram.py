from datetime import datetime

from pydantic import BaseModel


class TelegramConnectRequest(BaseModel):
    bot_token: str


class TelegramBotConfigUpdate(BaseModel):
    bot_token: str
    bot_username: str = ""


class TelegramBotConfigResponse(BaseModel):
    configured: bool
    bot_username: str | None = None
    has_token: bool = False
    verified_username: str | None = None


class TelegramStatusResponse(BaseModel):
    connected: bool
    bot_username: str | None = None
    chat_id: int | None = None
    status: str | None = None
    pairing_code: str | None = None
    pairing_link: str | None = None
    pairing_expires_at: datetime | None = None
