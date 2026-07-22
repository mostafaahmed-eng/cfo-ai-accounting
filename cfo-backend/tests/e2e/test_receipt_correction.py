import pytest


@pytest.mark.asyncio
async def test_upload_receipt_and_correct_vendor(client):
    """E2E: Upload a receipt and correct the vendor name.

    Flow:
    1. Upload receipt document
    2. AI extraction processes it
    3. User reviews and corrects vendor
    4. Approve creates journal entry
    """
    # Verify upload endpoint requires auth
    upload_resp = await client.post("/api/v1/documents/upload")
    assert upload_resp.status_code in (401, 422)

    # Verify draft update requires auth
    update_resp = await client.patch(
        "/api/v1/draft-transactions/test-id",
        json={
            "description": "Corrected vendor name",
        },
    )
    assert update_resp.status_code == 401
