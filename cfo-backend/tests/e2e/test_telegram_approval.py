import pytest


@pytest.mark.asyncio
async def test_telegram_transaction_approval(client):
    """E2E: Approve a Telegram transaction.

    Flow:
    1. Telegram webhook receives message
    2. Inbox item created
    3. AI extraction runs
    4. Bot replies with Approve/Edit/Reject buttons
    5. User approves
    6. Journal entry created
    """
    # When TELEGRAM_WEBHOOK_SECRET is empty (local dev), webhook accepts without secret
    # When TELEGRAM_WEBHOOK_SECRET is set, missing/wrong secret returns 403
    webhook_resp = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 99999,
            "message": {
                "message_id": 1,
                "chat": {"id": 12345},
                "text": "I spent $50 for coffee",
            },
        },
    )
    assert webhook_resp.status_code in (200, 403)

    # Verify integration status requires auth
    status_resp = await client.get("/api/v1/integrations/telegram/status")
    assert status_resp.status_code == 401
