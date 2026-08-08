from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.company import Company, CompanyMember
from app.models.draft_transaction import DraftTransaction
from app.models.user import User
from app.services.auth import create_access_token


async def _draft(db_session, company_id, status="ready_for_review"):
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        type="expense",
        amount=Decimal("10.0000"),
        tax_amount=Decimal("0.0000"),
        currency="USD",
        transaction_date=datetime.now(UTC).date(),
        description="Reject me",
        status=status,
    )
    db_session.add(draft)
    await db_session.flush()
    return draft


async def _user_with_role(db_session, company_id, role):
    user = User(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@example.com",
        name="Role User",
        password_hash=hash_password("testpass123"),
        language="en",
        timezone="UTC",
        status="active",
    )
    member = CompanyMember(
        id=uuid4(),
        company_id=str(company_id),
        user_id=str(user.id),
        role=role,
        status="active",
        joined_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db_session.add_all([user, member])
    await db_session.flush()
    return user


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["VIEWER", "ACCOUNTANT"])
async def test_non_approval_roles_cannot_reject(
    client, db_session, _setup_company_and_user, role
):
    company_id, _, _ = _setup_company_and_user
    draft = await _draft(db_session, company_id)
    actor = await _user_with_role(db_session, company_id, role)
    headers = {"Authorization": f"Bearer {create_access_token(str(actor.id))}"}

    response = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/reject", headers=headers
    )
    assert response.status_code == 403
    await db_session.refresh(draft)
    assert draft.status == "ready_for_review"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["VIEWER", "ACCOUNTANT"])
async def test_non_approval_roles_cannot_request_clarification(
    client, db_session, _setup_company_and_user, role
):
    company_id, _, _ = _setup_company_and_user
    draft = await _draft(db_session, company_id)
    actor = await _user_with_role(db_session, company_id, role)
    headers = {"Authorization": f"Bearer {create_access_token(str(actor.id))}"}

    response = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/request-clarification",
        headers=headers,
        json={"question": "Why?", "answer": "More info"},
    )
    assert response.status_code == 403
    await db_session.refresh(draft)
    assert draft.status == "ready_for_review"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "APPROVER"])
async def test_approval_roles_can_reject(
    client, db_session, _setup_company_and_user, role
):
    company_id, _, _ = _setup_company_and_user
    draft = await _draft(db_session, company_id)
    actor = await _user_with_role(db_session, company_id, role)
    headers = {"Authorization": f"Bearer {create_access_token(str(actor.id))}"}

    response = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/reject", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["OWNER", "ADMIN", "APPROVER"])
async def test_approval_roles_can_request_clarification(
    client, db_session, _setup_company_and_user, role
):
    company_id, _, _ = _setup_company_and_user
    draft = await _draft(db_session, company_id)
    actor = await _user_with_role(db_session, company_id, role)
    headers = {"Authorization": f"Bearer {create_access_token(str(actor.id))}"}

    response = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/request-clarification",
        headers=headers,
        json={"question": "Why?", "answer": "More info"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "needs_clarification"


@pytest.mark.asyncio
async def test_reject_from_foreign_company_is_hidden(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    foreign = Company(
        id=uuid4(),
        name="Foreign",
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )
    db_session.add(foreign)
    foreign_draft = await _draft(db_session, foreign.id)

    response = await client.post(
        f"/api/v1/draft-transactions/{foreign_draft.id}/reject",
        headers=headers,
    )
    # The OWNER's membership resolves to their own company, so the foreign
    # draft is invisible -> 404, never a cross-company write.
    assert response.status_code == 404
    await db_session.refresh(foreign_draft)
    assert foreign_draft.status == "ready_for_review"


@pytest.mark.asyncio
async def test_reject_requires_authentication(client):
    response = await client.post("/api/v1/draft-transactions/test-id/reject")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_request_clarification_requires_authentication(client):
    response = await client.post(
        "/api/v1/draft-transactions/test-id/request-clarification",
        json={"question": "?", "answer": "!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["approved", "posted", "rejected"])
async def test_immutable_drafts_cannot_be_rejected(
    client, db_session, _setup_company_and_user, status
):
    company_id, _, headers = _setup_company_and_user
    draft = await _draft(db_session, company_id, status=status)

    response = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/reject", headers=headers
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Draft not ready for review"
    await db_session.refresh(draft)
    assert draft.status == status


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["approved", "posted", "rejected"])
async def test_immutable_drafts_cannot_request_clarification(
    client, db_session, _setup_company_and_user, status
):
    company_id, _, headers = _setup_company_and_user
    draft = await _draft(db_session, company_id, status=status)

    response = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/request-clarification",
        headers=headers,
        json={"question": "?", "answer": "!"},
    )
    assert response.status_code == 400
    await db_session.refresh(draft)
    assert draft.status == status
