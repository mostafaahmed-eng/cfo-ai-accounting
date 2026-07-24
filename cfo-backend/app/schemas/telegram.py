from pydantic import BaseModel
from datetime import datetime


class TelegramConnectRequest(BaseModel):
    bot_token: str


class TelegramStatusResponse(BaseModel):
    connected: bool
    bot_username: str | None = None
    chat_id: int | None = None
    status: str | None = None
    pairing_code: str | None = None
    pairing_link: str | None = None
    pairing_expires_at: datetime | None = None
