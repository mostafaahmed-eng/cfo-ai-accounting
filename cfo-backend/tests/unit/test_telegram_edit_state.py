import pytest

from app.services import telegram_edit_state
from app.services.telegram_edit_state import TelegramEditState


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    async def set(self, key, value, *, ex):
        self.values[key] = value
        self.set_calls.append((key, ex))

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, key):
        self.values.pop(key, None)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_edit_state_is_scoped_and_expires(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(telegram_edit_state, "_redis", lambda: redis)
    monkeypatch.setattr(telegram_edit_state.settings, "TELEGRAM_EDIT_TTL_MINUTES", 15)
    state = TelegramEditState(
        connection_id="connection-a",
        company_id="company-a",
        chat_id=1001,
        draft_id="draft-a",
        field="amount",
    )

    await telegram_edit_state.set_edit_state(state)

    assert redis.set_calls == [("telegram:draft-edit:connection-a:company-a:1001", 900)]
    assert (
        await telegram_edit_state.get_edit_state(
            connection_id="connection-a",
            company_id="company-a",
            chat_id=1001,
        )
        == state
    )
    assert (
        await telegram_edit_state.get_edit_state(
            connection_id="connection-a",
            company_id="company-b",
            chat_id=1001,
        )
        is None
    )
    assert (
        await telegram_edit_state.get_edit_state(
            connection_id="connection-a",
            company_id="company-a",
            chat_id=2002,
        )
        is None
    )
