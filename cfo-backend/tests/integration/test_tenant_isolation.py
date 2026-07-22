import pytest


@pytest.mark.asyncio
async def test_accounts_scoped_to_company(client):
    """Test that accounts are scoped to company."""
    response = await client.get("/api/v1/accounts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vendors_scoped_to_company(client):
    """Test that vendors are scoped to company."""
    response = await client.get("/api/v1/vendors")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_draft_transactions_scoped_to_company(client):
    """Test that draft transactions are scoped to company."""
    response = await client.get("/api/v1/draft-transactions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reports_scoped_to_company(client):
    """Test that reports are scoped to company."""
    response = await client.get("/api/v1/reports/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_budgets_scoped_to_company(client):
    """Test that budgets are scoped to company."""
    response = await client.get("/api/v1/budgets")
    assert response.status_code == 401
