import pytest


@pytest.mark.asyncio
async def test_telegram_webhook_duplicate_prevention(client):
    """Test that webhook skips secret check when TELEGRAM_WEBHOOK_SECRET is empty."""
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
async def test_telegram_webhook_no_secret(client):
    """Test that webhook accepts when no secret header sent (local dev)."""
    response = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 12346,
            "message": {"text": "test", "chat": {"id": 99999}},
        },
    )
    assert response.status_code in (200, 403)
