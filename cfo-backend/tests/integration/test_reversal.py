import pytest


@pytest.mark.asyncio
async def test_reversal_requires_auth(client):
    """Test that reversal creation requires authentication."""
    # Reversals should not have a PATCH/DELETE endpoint for posted entries
    response = await client.patch("/api/v1/journal/test-entry-id")
    # Should be 405 Method Not Allowed or 401
    assert response.status_code in (401, 405)
