from datetime import UTC, datetime
from uuid import uuid4

import pytest
from limits.storage import RedisStorage

from app.config import get_settings
from app.limiter import limiter
from app.models.company import Company, CompanyMember


def _text_payload(text):
    return {"text": text, "language": "en"}


async def _add_second_company(db_session, user_id):
    company_b = uuid4()
    db_session.add(
        Company(
            id=company_b,
            name="Company B",
            country_code="US",
            base_currency="USD",
            fiscal_year_start=1,
            timezone="UTC",
        )
    )
    db_session.add(
        CompanyMember(
            id=uuid4(),
            company_id=str(company_b),
            user_id=str(user_id),
            role="OWNER",
            status="active",
            joined_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    )
    await db_session.flush()
    return company_b


@pytest.mark.asyncio
async def test_ai_endpoint_carries_rate_limit_headers(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user

    response = await client.post(
        "/api/v1/intake/text", json=_text_payload("header check"), headers=headers
    )

    assert response.status_code == 200
    assert response.headers.get("X-RateLimit-Limit") is not None


@pytest.mark.asyncio
async def test_ai_rate_limit_returns_429(client, db_session, _setup_company_and_user):
    company_id, _, headers = _setup_company_and_user
    settings = get_settings()
    limit = int(settings.RATE_LIMIT_AI.split("/")[0])

    for i in range(limit):
        response = await client.post(
            "/api/v1/intake/text", json=_text_payload(f"burst {i}"), headers=headers
        )
        assert response.status_code == 200

    response = await client.post(
        "/api/v1/intake/text", json=_text_payload("over limit"), headers=headers
    )

    assert response.status_code == 429
    assert response.headers.get("Retry-After") is not None


@pytest.mark.asyncio
async def test_ai_rate_limit_is_per_company(
    client, db_session, _setup_company_and_user
):
    company_a, user_id, headers = _setup_company_and_user
    company_b = await _add_second_company(db_session, user_id)
    settings = get_settings()
    limit = int(settings.RATE_LIMIT_AI.split("/")[0])

    headers_a = {**headers, "X-Company-ID": str(company_a)}
    headers_b = {**headers, "X-Company-ID": str(company_b)}

    for i in range(limit):
        response = await client.post(
            "/api/v1/intake/text", json=_text_payload(f"a {i}"), headers=headers_a
        )
        assert response.status_code == 200

    response = await client.post(
        "/api/v1/intake/text", json=_text_payload("a over"), headers=headers_a
    )
    assert response.status_code == 429

    response = await client.post(
        "/api/v1/intake/text", json=_text_payload("b allowed"), headers=headers_b
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ai_rate_limit_auth_unchanged(client):
    response = await client.post("/api/v1/intake/text", json=_text_payload("no auth"))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ai_rate_limit_fail_open_when_redis_down(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user

    original_storage = limiter._storage
    try:
        limiter._storage = RedisStorage("redis://127.0.0.1:1/0")
        response = await client.post(
            "/api/v1/intake/text", json=_text_payload("redis down"), headers=headers
        )
        assert response.status_code == 200
    finally:
        limiter._storage = original_storage
