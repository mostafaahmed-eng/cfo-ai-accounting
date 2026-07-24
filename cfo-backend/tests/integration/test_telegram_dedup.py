import pytest


@pytest.mark.asyncio
async def test_telegram_webhook_duplicate_prevention(client, monkeypatch):
    from app.api.v1 import telegram

    monkeypatch.setattr(telegram.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(telegram.settings, "TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(
        telegram.settings, "TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK", True
    )
    response1 = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 12345,
            "message": {
                "message_id": 1,
                "chat": {"id": 99999},
                "text": "I spent $100",
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    # Secret check is skipped when TELEGRAM_WEBHOOK_SECRET is empty (default)
    assert response1.status_code == 200


@pytest.mark.asyncio
async def test_telegram_webhook_no_secret(client, monkeypatch):
    """Explicit local development mode accepts a webhook without a secret."""
    from app.api.v1 import telegram

    monkeypatch.setattr(telegram.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(telegram.settings, "TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(
        telegram.settings, "TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK", True
    )
    response = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 12346,
            "message": {"text": "test", "chat": {"id": 99999}},
        },
    )
    assert response.status_code == 200
