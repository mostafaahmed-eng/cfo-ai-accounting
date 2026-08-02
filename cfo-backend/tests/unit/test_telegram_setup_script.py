import pytest

from app.scripts import telegram_setup


@pytest.mark.asyncio
async def test_missing_env_fails(monkeypatch):
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    assert await telegram_setup._main() == 1


@pytest.mark.asyncio
async def test_successful_setup(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com/")

    async def fake_call(token, method, payload):
        if method == "setWebhook":
            assert token == "123:abc"
            assert payload["url"] == "https://example.com/api/v1/telegram/webhook"
            assert payload["secret_token"] == "s3cret"
            return {"ok": True, "result": True}
        assert method == "getWebhookInfo"
        return {
            "ok": True,
            "result": {
                "url": "https://example.com/api/v1/telegram/webhook",
                "pending_update_count": 0,
            },
        }

    monkeypatch.setattr(telegram_setup, "_call", fake_call)
    assert await telegram_setup._main() == 0


@pytest.mark.asyncio
async def test_setwebhook_error_fails(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")

    async def fake_call(token, method, payload):
        return {"ok": False, "description": "wrong token"}

    monkeypatch.setattr(telegram_setup, "_call", fake_call)
    assert await telegram_setup._main() == 1
