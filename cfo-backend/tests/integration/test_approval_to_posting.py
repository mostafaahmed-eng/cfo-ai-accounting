import pytest


@pytest.mark.asyncio
async def test_approval_list_requires_auth(client):
    """Test approval list requires authentication."""
    response = await client.get("/api/v1/approval")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_draft_approve_requires_auth(client):
    """Test draft approval requires authentication."""
    response = await client.post("/api/v1/draft-transactions/test-id/approve")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_draft_reject_requires_auth(client):
    """Test draft rejection requires authentication."""
    response = await client.post("/api/v1/draft-transactions/test-id/reject")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_journal_entries_require_auth(client):
    """Test journal entries require authentication."""
    response = await client.get("/api/v1/journal")
    assert response.status_code == 401
