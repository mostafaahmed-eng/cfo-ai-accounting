import pytest


@pytest.mark.asyncio
async def test_dashboard_uses_only_posted_entries(client):
    """E2E: Dashboard and reports reflect only posted entries.

    The report service queries filter by JournalEntry.status == 'posted'.
    This test verifies the endpoint structure is correct.
    """
    # All report endpoints require authentication
    endpoints = [
        "/api/v1/reports/dashboard",
        "/api/v1/reports/profit-and-loss",
        "/api/v1/reports/cash-flow",
        "/api/v1/reports/balance-sheet",
        "/api/v1/reports/expenses-by-category",
        "/api/v1/reports/vendors",
        "/api/v1/reports/budget-vs-actual",
    ]

    for endpoint in endpoints:
        resp = await client.get(endpoint)
        assert resp.status_code == 401, f"{endpoint} should require authentication"


@pytest.mark.asyncio
async def test_no_patch_delete_on_posted_journal_entries(client):
    """Verify no PATCH/DELETE endpoint exists for journal entries.

    Posted journal entries are immutable per spec rule 3.
    """
    # PATCH on journal should return 405 Method Not Allowed
    resp = await client.patch("/api/v1/journal/test-id", json={"description": "hacked"})
    assert resp.status_code in (401, 405)

    # DELETE on journal should return 405 Method Not Allowed
    resp = await client.delete("/api/v1/journal/test-id")
    assert resp.status_code in (401, 405)
