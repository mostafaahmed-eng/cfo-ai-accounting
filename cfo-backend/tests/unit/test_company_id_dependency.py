from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.enums import UserStatus
from app.models.company import Company, CompanyMember
from app.models.user import User


def _make_user(email="multi@example.com"):
    return User(
        id=uuid4(),
        email=email,
        name="Multi Co User",
        password_hash="irrelevant",
        language="en",
        timezone="UTC",
        status=UserStatus.active,
    )


def _make_company(name="Test Co"):
    return Company(
        id=uuid4(),
        name=name,
        country_code="US",
        base_currency="USD",
    )


def _make_membership(user_id, company_id, role="MEMBER", status="active"):
    return CompanyMember(
        id=uuid4(),
        user_id=user_id,
        company_id=company_id,
        role=role,
        status=status,
        joined_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


# --- Tests that exercise company membership resolution directly ---


@pytest.mark.asyncio
async def test_single_membership_returns_that_company(db_session):
    """One active membership → returns that membership's company_id."""
    from app.dependencies import resolve_company_membership

    user = _make_user("single@example.com")
    company = _make_company("Single Co")
    membership = _make_membership(user.id, company.id, role="MEMBER")

    db_session.add_all([user, company, membership])
    await db_session.flush()

    resolved = await resolve_company_membership(user=user, db=db_session)
    assert resolved.company_id == company.id


@pytest.mark.asyncio
async def test_multiple_memberships_require_explicit_selection(db_session):
    """Multiple active memberships never trigger an implicit company choice."""
    from fastapi import HTTPException

    from app.dependencies import resolve_company_membership

    user = _make_user("owner@example.com")
    company_member = _make_company("Member Co")
    company_owner = _make_company("Owner Co")

    mem1 = _make_membership(user.id, company_member.id, role="MEMBER")
    mem2 = _make_membership(user.id, company_owner.id, role="OWNER")

    db_session.add_all([user, company_member, company_owner, mem1, mem2])
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_company_membership(user=user, db=db_session)
    assert exc_info.value.status_code == 409

    resolved = await resolve_company_membership(
        user=user,
        db=db_session,
        selected_company_id=str(company_owner.id),
    )
    assert resolved.company_id == company_owner.id


@pytest.mark.asyncio
async def test_unknown_explicit_membership_fails_safely(db_session):
    from fastapi import HTTPException

    from app.dependencies import resolve_company_membership

    user = _make_user("noowner@example.com")
    co_a = _make_company("Alpha Co")
    co_b = _make_company("Beta Co")

    mem_a = _make_membership(user.id, co_a.id, role="ADMIN")
    mem_b = _make_membership(user.id, co_b.id, role="MEMBER")

    db_session.add_all([user, co_a, co_b, mem_a, mem_b])
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_company_membership(
            user=user,
            db=db_session,
            selected_company_id=str(uuid4()),
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_no_memberships_raises_403(db_session):
    """User with zero active memberships → 403."""
    from fastapi import HTTPException

    from app.dependencies import resolve_company_membership

    user = _make_user("lonely@example.com")
    db_session.add(user)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_company_membership(user=user, db=db_session)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_only_inactive_memberships_raises_403(db_session):
    """User has memberships but all are disabled → 403."""
    from fastapi import HTTPException

    from app.dependencies import resolve_company_membership

    user = _make_user("disabled@example.com")
    company = _make_company("Disabled Co")
    membership = _make_membership(user.id, company.id, role="OWNER", status="disabled")

    db_session.add_all([user, company, membership])
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await resolve_company_membership(user=user, db=db_session)
    assert exc_info.value.status_code == 403


# --- Integration test through the real HTTP client ---


@pytest.mark.asyncio
async def test_company_id_via_api(client, db_session):
    """End-to-end: login a user with memberships, call an endpoint that uses get_current_company_id."""
    from app.core.security import hash_password

    user = _make_user("api@example.com")
    user.password_hash = hash_password("testpass")
    company = _make_company("API Co")
    membership = _make_membership(user.id, company.id, role="OWNER")

    db_session.add_all([user, company, membership])
    await db_session.flush()

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "api@example.com",
            "password": "testpass",
        },
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Call an endpoint that resolves company_id
    accounts_resp = await client.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Should succeed (200) — proves get_current_company_id returned the right company
    assert accounts_resp.status_code == 200
