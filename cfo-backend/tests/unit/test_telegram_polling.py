import asyncio
import json

import httpx
import pytest

from app.services import telegram_polling


class _Settings:
    TELEGRAM_BOT_TOKEN = "test-token"
    TELEGRAM_WEBHOOK_SECRET = "test-secret"
    TELEGRAM_POLLING_INTERNAL_WEBHOOK_URL = (
        "http://backend:8000/api/v1/telegram/webhook"
    )
    TELEGRAM_POLLING_OFFSET_FILE = "/tmp/telegram_poll_offset"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(asyncio, "sleep", noop)


def _update(update_id: int) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 100 + update_id,
            "chat": {"id": 111},
            "text": "/start 12345",
        },
    }


def test_delivers_update_and_advances_offset(tmp_path, monkeypatch):
    delivered = []
    offset_file = tmp_path / "offset"

    def handler(request):
        if "getUpdates" in str(request.url):
            return httpx.Response(
                200,
                json={"ok": True, "result": [_update(42)]},
            )
        delivered.append(request)
        assert request.headers["X-Telegram-Bot-Api-Secret-Token"] == "test-secret"
        assert json.loads(request.content)["update_id"] == 42
        return httpx.Response(200, json={"status": "ok"})

    async def scenario():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await telegram_polling.run(
                settings=_Settings(),
                client=client,
                offset_path=str(offset_file),
                max_cycles=1,
            )
            return result

    result = asyncio.run(scenario())
    assert result == 0
    assert len(delivered) == 1
    assert offset_file.read_text() == "43"


def test_webhook_rate_limit_retries_until_success(tmp_path):
    webhook_calls = {"count": 0}

    def handler(request):
        if "getUpdates" in str(request.url):
            return httpx.Response(
                200,
                json={"ok": True, "result": [_update(7)]},
            )
        webhook_calls["count"] += 1
        if webhook_calls["count"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"status": "ok"})

    offset_file = tmp_path / "offset"

    async def scenario():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await telegram_polling.run(
                settings=_Settings(),
                client=client,
                offset_path=str(offset_file),
                max_cycles=1,
            )
            return result

    result = asyncio.run(scenario())
    assert result == 0
    assert webhook_calls["count"] == 2
    assert offset_file.read_text() == "8"


def test_webhook_conflict_does_not_advance_offset(tmp_path):
    webhook_calls = {"count": 0}

    def handler(request):
        if "getUpdates" in str(request.url):
            return httpx.Response(409)
        webhook_calls["count"] += 1
        return httpx.Response(200, json={"status": "ok"})

    offset_file = tmp_path / "offset"
    offset_file.write_text("99")

    async def scenario():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await telegram_polling.run(
                settings=_Settings(),
                client=client,
                offset_path=str(offset_file),
                max_cycles=2,
            )
            return result

    result = asyncio.run(scenario())
    assert result == 0
    assert webhook_calls["count"] == 0
    assert offset_file.read_text() == "99"


def test_missing_webhook_url_returns_1():
    settings = _Settings()
    settings.TELEGRAM_POLLING_INTERNAL_WEBHOOK_URL = ""
    assert asyncio.run(telegram_polling.run(settings=settings, max_cycles=1)) == 1
