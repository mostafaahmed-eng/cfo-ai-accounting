from pydantic import BaseModel


class TelegramConnectRequest(BaseModel):
    bot_token: str


class TelegramStatusResponse(BaseModel):
    connected: bool
    bot_username: str | None = None
    chat_id: int | None = None
    status: str | None = None
