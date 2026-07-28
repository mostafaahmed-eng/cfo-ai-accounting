import json
from dataclasses import asdict, dataclass

from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()


@dataclass
class TelegramEditState:
    connection_id: str
    company_id: str
    chat_id: int
    draft_id: str
    field: str


def _key(connection_id: str, company_id: str, chat_id: int) -> str:
    return f"telegram:draft-edit:{connection_id}:{company_id}:{chat_id}"


def _redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def set_edit_state(state: TelegramEditState) -> None:
    client = _redis()
    try:
        await client.set(
            _key(state.connection_id, state.company_id, state.chat_id),
            json.dumps(asdict(state)),
            ex=settings.TELEGRAM_EDIT_TTL_MINUTES * 60,
        )
    finally:
        await client.aclose()


async def get_edit_state(
    *, connection_id: str, company_id: str, chat_id: int
) -> TelegramEditState | None:
    client = _redis()
    try:
        payload = await client.get(_key(connection_id, company_id, chat_id))
    finally:
        await client.aclose()
    if not payload:
        return None
    try:
        state = TelegramEditState(**json.loads(payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        await clear_edit_state(
            connection_id=connection_id,
            company_id=company_id,
            chat_id=chat_id,
        )
        return None
    if (
        state.connection_id != connection_id
        or state.company_id != company_id
        or state.chat_id != chat_id
    ):
        return None
    return state


async def clear_edit_state(
    *, connection_id: str, company_id: str, chat_id: int
) -> None:
    client = _redis()
    try:
        await client.delete(_key(connection_id, company_id, chat_id))
    finally:
        await client.aclose()
