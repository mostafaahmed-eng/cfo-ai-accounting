from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.ai_extraction import AIExtraction
from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyMember
from app.models.document import Document
from app.models.draft_transaction import DraftTransaction
from app.models.inbox_item import InboxItem
from app.models.vendor import Vendor


async def _draft(db_session, company_id, **overrides):
    values = {
        "id": uuid4(),
        "company_id": company_id,
        "type": "expense",
        "amount": Decimal("10.0000"),
        "tax_amount": Decimal("0.0000"),
        "currency": "USD",
        "transaction_date": date(2026, 7, 25),
        "description": "Original description",
        "reference_number": "OLD-1",
        "status": "ready_for_review",
        "duplicate_status": "unique",
    }
    values.update(overrides)
    draft = DraftTransaction(**values)
    db_session.add(draft)
    await db_session.flush()
    return draft


@pytest.mark.asyncio
async def test_dashboard_edits_supported_fields_with_decimal_precision(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    vendor = Vendor(
        id=uuid4(),
        company_id=company_id,
        name="Correct Vendor",
        normalized_name="correct vendor",
        is_active=True,
    )
    db_session.add(vendor)
    draft = await _draft(db_session, company_id)

    response = await client.patch(
        f"/api/v1/draft-transactions/{draft.id}",
        headers=headers,
        json={
            "vendor_id": str(vendor.id),
            "amount": "0.1001",
            "currency": "egp",
            "transaction_date": "2026-07-24",
            "description": " Corrected purchase ",
            "reference_number": " INV-22 ",
            "type": "expense",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["vendor_id"] == str(vendor.id)
    assert payload["amount"] == 0.1001
    assert payload["currency"] == "EGP"
    assert payload["transaction_date"] == "2026-07-24"
    assert payload["description"] == "Corrected purchase"
    assert payload["reference_number"] == "INV-22"
    await db_session.refresh(draft)
    assert draft.amount == Decimal("0.1001")
    assert draft.tax_amount == Decimal("0.0000")
    assert draft.status == "ready_for_review"

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.entity_id == str(draft.id),
                AuditLog.action == "draft.updated",
            )
        )
    ).scalar_one()
    assert audit.actor_type == "user"
    assert audit.after_data["source"] == "dashboard"
    assert set(audit.after_data["fields_changed"]) == {
        "amount",
        "currency",
        "description",
        "reference_number",
        "transaction_date",
        "vendor_id",
    }
    serialized = str(audit.before_data) + str(audit.after_data)
    assert "token" not in serialized.casefold()
    assert "provider" not in serialized.casefold()


@pytest.mark.asyncio
async def test_partial_patch_preserves_unsupplied_fields(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    draft = await _draft(db_session, company_id)

    response = await client.patch(
        f"/api/v1/draft-transactions/{draft.id}",
        headers=headers,
        json={"description": "Only this changed"},
    )

    assert response.status_code == 200
    await db_session.refresh(draft)
    assert draft.description == "Only this changed"
    assert draft.amount == Decimal("10.0000")
    assert draft.currency == "USD"
    assert draft.reference_number == "OLD-1"


@pytest.mark.asyncio
async def test_repeated_identical_patch_is_idempotent(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    draft = await _draft(db_session, company_id)
    url = f"/api/v1/draft-transactions/{draft.id}"

    first = await client.patch(url, headers=headers, json={"description": "Retry-safe"})
    second = await client.patch(
        url, headers=headers, json={"description": "Retry-safe"}
    )

    assert first.status_code == second.status_code == 200
    audit_count = (
        await db_session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.entity_id == str(draft.id),
                AuditLog.action == "draft.updated",
            )
        )
    ).scalar_one()
    assert audit_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"currency": "US"}, 422),
        ({"amount": "0"}, 422),
        ({"transaction_date": "not-a-date"}, 422),
        ({"type": "purchase"}, 422),
    ],
)
async def test_invalid_edits_are_rejected(
    client, db_session, _setup_company_and_user, payload, status
):
    company_id, _, headers = _setup_company_and_user
    draft = await _draft(db_session, company_id)
    response = await client.patch(
        f"/api/v1/draft-transactions/{draft.id}",
        headers=headers,
        json=payload,
    )
    assert response.status_code == status


@pytest.mark.asyncio
async def test_foreign_draft_is_hidden_and_viewer_cannot_edit(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, headers = _setup_company_and_user
    foreign_company = Company(
        id=uuid4(),
        name="Foreign",
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )
    db_session.add(foreign_company)
    foreign = await _draft(db_session, foreign_company.id)

    hidden = await client.patch(
        f"/api/v1/draft-transactions/{foreign.id}",
        headers=headers,
        json={"description": "Attack"},
    )
    assert hidden.status_code == 404

    membership = (
        await db_session.execute(
            select(CompanyMember).where(
                CompanyMember.company_id == company_id,
                CompanyMember.user_id == user_id,
            )
        )
    ).scalar_one()
    membership.role = "VIEWER"
    own = await _draft(db_session, company_id)
    await db_session.flush()
    forbidden = await client.patch(
        f"/api/v1/draft-transactions/{own.id}",
        headers=headers,
        json={"description": "Attack"},
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("immutable_status", ["approved", "posted", "rejected"])
async def test_immutable_drafts_cannot_be_edited(
    client, db_session, _setup_company_and_user, immutable_status
):
    company_id, _, headers = _setup_company_and_user
    draft = await _draft(db_session, company_id, status=immutable_status)
    response = await client.patch(
        f"/api/v1/draft-transactions/{draft.id}",
        headers=headers,
        json={"description": "No"},
    )
    assert response.status_code == 409
    assert draft.description == "Original description"


@pytest.mark.asyncio
async def test_edit_does_not_create_intake_artifacts_or_second_draft(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    draft = await _draft(db_session, company_id)
    models = (DraftTransaction, InboxItem, Document, AIExtraction)
    before = {
        model: (
            await db_session.execute(select(func.count()).select_from(model))
        ).scalar_one()
        for model in models
    }

    response = await client.patch(
        f"/api/v1/draft-transactions/{draft.id}",
        headers=headers,
        json={"amount": "12.3456"},
    )
    assert response.status_code == 200
    after = {
        model: (
            await db_session.execute(select(func.count()).select_from(model))
        ).scalar_one()
        for model in models
    }
    assert after == before


@pytest.mark.asyncio
async def test_duplicate_status_is_reevaluated_without_silent_warning_removal(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    original = await _draft(
        db_session,
        company_id,
        description="Same",
        status="posted",
    )
    duplicate = await _draft(
        db_session,
        company_id,
        description="Different",
        duplicate_status="likely_duplicate",
        duplicate_of_id=original.id,
    )

    response = await client.patch(
        f"/api/v1/draft-transactions/{duplicate.id}",
        headers=headers,
        json={"amount": "11.0000"},
    )
    assert response.status_code == 200
    await db_session.refresh(duplicate)
    assert duplicate.duplicate_status == "unchecked"
    assert (
        duplicate.duplicate_reason
        == "Draft fields changed; duplicate review is required"
    )
