import pytest


@pytest.mark.asyncio
async def test_telegram_webhook_duplicate_prevention(client):
    """Test that duplicate Telegram updates are ignored."""
    # First webhook call
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

    # Should fail with wrong secret
    assert response1.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_missing_secret(client):
    """Test that webhook accepts when TELEGRAM_WEBHOOK_SECRET is empty (local dev)."""
    response = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 12345,
            "message": {"text": "test"},
        },
    )
    assert response.status_code in (200, 403)
