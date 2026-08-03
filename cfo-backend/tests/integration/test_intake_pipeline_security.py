import io
from datetime import date
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select

from app.models.ai_extraction import AIExtraction
from app.models.document import Document
from app.models.draft_transaction import DraftTransaction
from app.models.inbox_item import InboxItem
from app.services.intake import create_text_inbox
from app.tasks.ai_extraction import _finalize_extraction

pytestmark = pytest.mark.asyncio


def _png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), color="white").save(output, format="PNG")
    return output.getvalue()


def _valid_extraction(amount=42.5, reference="INV-42"):
    return {
        "extracted": {
            "document_type": "receipt",
            "transaction_type": "expense",
            "amount": amount,
            "tax_amount": 0,
            "currency": "USD",
            "transaction_date": "2026-01-02",
            "vendor": {"name": "Example Vendor", "tax_number": None},
            "description": "Office supplies",
            "category_hint": "office",
            "payment_method_hint": None,
            "reference_number": reference,
            "language": "en",
            "confidence": {
                "overall": 0.9,
                "amount": 0.9,
                "currency": 0.9,
                "date": 0.9,
                "category": 0.8,
            },
            "needs_clarification": False,
            "questions": [],
        },
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost": 0.001,
        "processing_ms": 25,
    }


async def test_text_intake_is_persisted_and_dispatched_once(
    client, db_session, _setup_company_and_user, monkeypatch
):
    company_id, _, headers = _setup_company_and_user
    dispatched = []
    monkeypatch.setattr(
        "app.api.v1.intake.run_ai_extraction.delay",
        lambda item_id: dispatched.append(item_id),
    )
    payload = {
        "text": "Paid USD 42.50 for office supplies",
        "idempotency_key": f"text-{uuid4()}",
    }

    first = await client.post("/api/v1/intake/text", json=payload, headers=headers)
    second = await client.post("/api/v1/intake/text", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "queued"
    assert dispatched == [first.json()["id"]]
    item = (
        await db_session.execute(
            select(InboxItem).where(
                InboxItem.id == first.json()["id"],
                InboxItem.company_id == company_id,
            )
        )
    ).scalar_one()
    assert item.original_text == payload["text"]
    assert len(item.content_hash) == 64


async def test_normalized_text_retry_is_one_company_scoped_item(
    db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    first = await create_text_inbox(
        db_session,
        company_id=company_id,
        text="Paid  USD 42.50",
        language="en",
        source="web_text",
        submitted_by=user_id,
    )
    second = await create_text_inbox(
        db_session,
        company_id=company_id,
        text=" paid usd 42.50 ",
        language="en",
        source="web_text",
        submitted_by=user_id,
    )
    assert first.created is True
    assert second.created is False
    assert first.item.id == second.item.id


async def test_document_upload_links_records_and_exact_retry_is_idempotent(
    client, db_session, _setup_company_and_user, monkeypatch
):
    company_id, _, headers = _setup_company_and_user
    uploaded = []
    dispatched = []

    async def fake_upload(key, content, mime):
        uploaded.append((key, content, mime))

    monkeypatch.setattr(
        "app.api.v1.documents.storage_client.upload_file",
        fake_upload,
    )
    monkeypatch.setattr(
        "app.api.v1.documents.process_receipt.delay",
        lambda inbox_id, document_id: dispatched.append((inbox_id, document_id)),
    )
    content = _png()

    first = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("../../receipt.png", content, "image/png")},
        headers=headers,
    )
    second = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("again.png", content, "image/png")},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(uploaded) == 1
    assert len(dispatched) == 1
    assert ".." not in uploaded[0][0]
    document = (
        await db_session.execute(
            select(Document).where(
                Document.id == first.json()["id"],
                Document.company_id == company_id,
            )
        )
    ).scalar_one()
    inbox = (
        await db_session.execute(
            select(InboxItem).where(
                InboxItem.id == document.inbox_item_id,
                InboxItem.company_id == company_id,
            )
        )
    ).scalar_one()
    assert inbox.status == "queued"


async def test_upload_mismatch_and_cross_company_lookup_fail(
    client, _setup_company_and_user
):
    _, _, headers = _setup_company_and_user
    mismatch = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("fake.jpg", _png(), "image/jpeg")},
        headers=headers,
    )
    foreign = await client.get(
        f"/api/v1/documents/{uuid4()}",
        headers=headers,
    )
    assert mismatch.status_code == 415
    assert foreign.status_code == 404


async def test_valid_provider_result_creates_one_review_draft_without_accounts(
    db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    item = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="web_text",
        content_type="text",
        original_text="Paid USD 42.50 for office supplies",
        detected_language="en",
        status="processing",
        submitted_by=user_id,
        content_hash="a" * 64,
        duplicate_status="unique",
    )
    db_session.add(item)
    await db_session.flush()

    first = await _finalize_extraction(db_session, item, _valid_extraction())
    second = await _finalize_extraction(db_session, item, _valid_extraction())

    assert first["status"] == "review_required"
    assert second["status"] == "already_processed"
    drafts = (
        (
            await db_session.execute(
                select(DraftTransaction).where(
                    DraftTransaction.inbox_item_id == item.id,
                    DraftTransaction.company_id == company_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(drafts) == 1
    assert drafts[0].category_account_id is None
    assert drafts[0].payment_account_id is None
    extraction = (
        await db_session.execute(
            select(AIExtraction).where(
                AIExtraction.inbox_item_id == item.id,
                AIExtraction.company_id == company_id,
            )
        )
    ).scalar_one()
    assert extraction.input_tokens == 100
    assert extraction.raw_response == {"response_received": True}


async def test_invalid_provider_output_creates_no_draft(
    db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    item = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="web_text",
        content_type="text",
        original_text="incomplete",
        detected_language="en",
        status="processing",
        submitted_by=user_id,
        content_hash="b" * 64,
        duplicate_status="unique",
    )
    db_session.add(item)
    await db_session.flush()

    result = await _finalize_extraction(
        db_session,
        item,
        {"extracted": {"amount": 10}, "input_tokens": 1, "output_tokens": 1},
    )
    assert result == {"status": "failed", "reason": "invalid_extraction"}
    drafts = (
        (
            await db_session.execute(
                select(DraftTransaction).where(
                    DraftTransaction.inbox_item_id == item.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert drafts == []
    assert item.error_message == "Could not extract the required financial fields"


async def test_structured_duplicate_is_flagged_but_preserved(
    db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    first = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="web_text",
        content_type="text",
        original_text="first",
        detected_language="en",
        status="processing",
        submitted_by=user_id,
        content_hash="c" * 64,
        duplicate_status="unique",
    )
    second = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="web_text",
        content_type="text",
        original_text="second",
        detected_language="en",
        status="processing",
        submitted_by=user_id,
        content_hash="d" * 64,
        duplicate_status="unique",
    )
    db_session.add_all([first, second])
    await db_session.flush()

    await _finalize_extraction(db_session, first, _valid_extraction())
    result = await _finalize_extraction(db_session, second, _valid_extraction())
    assert result["duplicate_status"] == "likely_duplicate"
    drafts = (
        (
            await db_session.execute(
                select(DraftTransaction).where(
                    DraftTransaction.company_id == company_id,
                    DraftTransaction.inbox_item_id.in_([first.id, second.id]),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(drafts) == 2


async def test_foreign_or_merely_similar_drafts_are_not_flagged(
    db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    from app.models.company import Company

    other_company = Company(
        id=uuid4(),
        name="Foreign Duplicate Candidate",
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )
    foreign_draft = DraftTransaction(
        id=uuid4(),
        company_id=other_company.id,
        type="expense",
        amount=42.5,
        tax_amount=0,
        currency="USD",
        transaction_date=date(2026, 1, 2),
        description="[AI] Office supplies — Example Vendor",
        reference_number="INV-42",
        status="ready_for_review",
        duplicate_status="unique",
    )
    local_item = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="web_text",
        content_type="text",
        original_text="A separate purchase",
        detected_language="en",
        status="processing",
        submitted_by=user_id,
        content_hash="e" * 64,
        duplicate_status="unique",
    )
    db_session.add_all([other_company, foreign_draft, local_item])
    await db_session.flush()

    result = await _finalize_extraction(
        db_session,
        local_item,
        _valid_extraction(reference="LOCAL-UNIQUE"),
    )
    assert result["duplicate_status"] == "unique"


async def test_provider_result_without_date_creates_draft_with_default(
    db_session, _setup_company_and_user
):
    from datetime import UTC, datetime

    company_id, user_id, _ = _setup_company_and_user
    extraction_result = _valid_extraction()
    extraction_result["extracted"]["transaction_date"] = None
    extraction_result["extracted"]["transaction_type"] = "unknown"
    item = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="web_text",
        content_type="text",
        original_text="I spent 100 EGP on hosting",
        detected_language="en",
        status="processing",
        submitted_by=user_id,
        content_hash="f" * 64,
        duplicate_status="unique",
    )
    db_session.add(item)
    await db_session.flush()

    result = await _finalize_extraction(db_session, item, extraction_result)

    assert result["status"] == "review_required"
    draft = (
        await db_session.execute(
            select(DraftTransaction).where(
                DraftTransaction.inbox_item_id == item.id,
                DraftTransaction.company_id == company_id,
            )
        )
    ).scalar_one()
    assert draft.transaction_date == datetime.now(UTC).date()
    assert draft.type == "expense"
    assert draft.status == "ready_for_review"
