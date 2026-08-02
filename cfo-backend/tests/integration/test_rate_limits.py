import pytest

from app.config import get_settings


def _webhook_payload(update_id):
    return {
        "update_id": update_id,
        "message": {"message_id": 1, "chat": {"id": 99999}, "text": "test"},
    }


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429(client):
    settings = get_settings()
    limit_per_minute = int(settings.RATE_LIMIT_LOGIN.split("/")[0])

    for _ in range(limit_per_minute):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass"},
        )
        assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_webhook_rate_limit_returns_429(client, monkeypatch):
    from app.api.v1 import telegram

    monkeypatch.setattr(telegram.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(telegram.settings, "TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(
        telegram.settings, "TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK", True
    )

    settings = get_settings()
    limit_per_minute = int(settings.RATE_LIMIT_WEBHOOK.split("/")[0])

    for i in range(limit_per_minute):
        response = await client.post(
            "/api/v1/telegram/webhook",
            json=_webhook_payload(20000 + i),
        )
        assert response.status_code == 200

    response = await client.post(
        "/api/v1/telegram/webhook",
        json=_webhook_payload(29999),
    )
    assert response.status_code == 429
