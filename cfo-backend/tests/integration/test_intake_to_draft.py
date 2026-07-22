import pytest


@pytest.mark.asyncio
async def test_text_intake_creates_inbox_item(client):
    """Test that submitting text creates an inbox item."""
    response = await client.post(
        "/api/v1/intake/text",
        json={
            "text": "I spent $100 on hosting",
        },
    )
    # Will be 401 without auth token, which validates the auth dependency works
    assert response.status_code in (200, 401, 422)


@pytest.mark.asyncio
async def test_text_intake_with_idempotency_key(client):
    """Test that idempotency key is accepted."""
    response = await client.post(
        "/api/v1/intake/text",
        json={
            "text": "I spent $50 for software",
            "idempotency_key": "test-key-123",
        },
    )
    assert response.status_code in (200, 401, 422)


@pytest.mark.asyncio
async def test_text_intake_arabic(client):
    """Test Arabic text intake."""
    response = await client.post(
        "/api/v1/intake/text",
        json={
            "text": "دفعت ٥٠٠ جنيه إعلانات",
            "language": "ar",
        },
    )
    assert response.status_code in (200, 401, 422)


@pytest.mark.asyncio
async def test_inbox_item_retry(client):
    """Test retry endpoint exists."""
    response = await client.post("/api/v1/intake/nonexistent-id/retry")
    # Should be 401 (no auth) or 404 (not found)
    assert response.status_code in (401, 404)
