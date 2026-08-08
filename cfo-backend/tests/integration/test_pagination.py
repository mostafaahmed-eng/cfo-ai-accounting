from uuid import uuid4

import pytest

from app.models.company import Company
from app.models.vendor import Vendor


async def _add_vendors(db_session, company_id, count, prefix="Vendor"):
    for i in range(count):
        db_session.add(
            Vendor(
                id=uuid4(),
                company_id=str(company_id),
                name=f"{prefix} {i:02d}",
                normalized_name=f"{prefix.lower()} {i:02d}",
                is_active=True,
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_list_default_page_and_total_count(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    await _add_vendors(db_session, company_id, 60)

    response = await client.get("/api/v1/vendors", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 50
    assert response.headers["X-Total-Count"] == "60"


@pytest.mark.asyncio
async def test_list_custom_limit(client, db_session, _setup_company_and_user):
    company_id, _, headers = _setup_company_and_user
    await _add_vendors(db_session, company_id, 25)

    response = await client.get("/api/v1/vendors?limit=10", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 10
    assert body[0]["name"] == "Vendor 00"
    assert response.headers["X-Total-Count"] == "25"


@pytest.mark.asyncio
async def test_list_offset_behavior(client, db_session, _setup_company_and_user):
    company_id, _, headers = _setup_company_and_user
    await _add_vendors(db_session, company_id, 30)

    response = await client.get("/api/v1/vendors?limit=10&offset=20", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 10
    assert body[0]["name"] == "Vendor 20"

    response = await client.get("/api/v1/vendors?limit=10&offset=100", headers=headers)
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "30"


@pytest.mark.asyncio
async def test_list_limit_and_offset_validation(client, _setup_company_and_user):
    company_id, _, headers = _setup_company_and_user

    for query in ("limit=0", "limit=-5", "limit=201", "offset=-1"):
        response = await client.get(f"/api/v1/vendors?{query}", headers=headers)
        assert response.status_code == 422, query


@pytest.mark.asyncio
async def test_list_empty_results(client, _setup_company_and_user):
    company_id, _, headers = _setup_company_and_user

    response = await client.get("/api/v1/vendors", headers=headers)

    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_list_scoped_to_company(client, db_session, _setup_company_and_user):
    company_id, _, headers = _setup_company_and_user
    await _add_vendors(db_session, company_id, 3)
    other_company = uuid4()
    db_session.add(
        Company(
            id=other_company,
            name="Other Company",
            country_code="US",
            base_currency="USD",
            fiscal_year_start=1,
            timezone="UTC",
        )
    )
    await _add_vendors(db_session, other_company, 5, prefix="Other")

    response = await client.get("/api/v1/vendors", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert response.headers["X-Total-Count"] == "3"
    assert all(item["name"].startswith("Vendor") for item in body)


@pytest.mark.asyncio
async def test_list_requires_auth(client):
    response = await client.get("/api/v1/vendors?limit=10")
    assert response.status_code == 401
