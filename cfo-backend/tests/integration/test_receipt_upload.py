import pytest


@pytest.mark.asyncio
async def test_upload_endpoint_exists(client):
    """Test document upload endpoint exists and validates auth."""
    response = await client.post("/api/v1/documents/upload")
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_document_download_url_requires_auth(client):
    """Test that download URL requires authentication."""
    response = await client.get("/api/v1/documents/test-id/download-url")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_document_delete_requires_auth(client):
    """Test that document deletion requires authentication."""
    response = await client.delete("/api/v1/documents/test-id")
    assert response.status_code == 401
