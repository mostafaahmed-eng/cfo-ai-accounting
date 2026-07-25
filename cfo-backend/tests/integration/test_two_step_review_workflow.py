from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.draft_transaction import DraftTransaction
from app.models.inbox_item import InboxItem
from app.models.journal import JournalEntry, JournalLine


def _inbox(company_id, text: str) -> InboxItem:
    return InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="web_text",
        content_type="text",
        original_text=text,
        detected_language="en",
        status="review_required",
        content_hash=uuid4().hex * 2,
        duplicate_status="unique",
    )


@pytest.mark.asyncio
async def test_dashboard_approval_posts_balanced_entry_and_archives_inbox(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    inbox = _inbox(company_id, "Paid USD 25 for supplies")
    category = Account(
        id=uuid4(),
        company_id=company_id,
        code="5900",
        name_en="Review Expense",
        type="expense",
        subtype="general",
        is_active=True,
    )
    payment = Account(
        id=uuid4(),
        company_id=company_id,
        code="1099",
        name_en="Review Cash",
        type="asset",
        subtype="cash",
        is_payment_account=True,
        is_active=True,
    )
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        inbox_item_id=inbox.id,
        type="expense",
        amount=25,
        tax_amount=0,
        currency="USD",
        transaction_date=datetime.now(timezone.utc).date(),
        description="Review expense",
        status="ready_for_review",
    )
    db_session.add_all([inbox, category, payment, draft])
    await db_session.flush()

    update = await client.patch(
        f"/api/v1/draft-transactions/{draft.id}",
        json={
            "category_account_id": str(category.id),
            "payment_account_id": str(payment.id),
        },
        headers=headers,
    )
    assert update.status_code == 200

    approved = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "posted"
    assert inbox.status == "archived"

    entry = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_id == str(draft.id))
        )
    ).scalar_one()
    lines = (
        (
            await db_session.execute(
                select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(lines) == 2
    assert sum(float(line.debit) for line in lines) == sum(
        float(line.credit) for line in lines
    )

    active = await client.get("/api/v1/intake", headers=headers)
    archived = await client.get("/api/v1/intake?status=archived", headers=headers)
    assert active.status_code == 200
    assert all(row["id"] != str(inbox.id) for row in active.json())
    assert [row["id"] for row in archived.json()] == [str(inbox.id)]


@pytest.mark.asyncio
async def test_dashboard_reject_archives_linked_inbox(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    inbox = _inbox(company_id, "Reject this item")
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        inbox_item_id=inbox.id,
        type="expense",
        amount=10,
        tax_amount=0,
        currency="USD",
        transaction_date=datetime.now(timezone.utc).date(),
        description="Reject me",
        status="ready_for_review",
    )
    db_session.add_all([inbox, draft])
    await db_session.flush()

    rejected = await client.post(
        f"/api/v1/draft-transactions/{draft.id}/reject",
        headers=headers,
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert inbox.status == "archived"
