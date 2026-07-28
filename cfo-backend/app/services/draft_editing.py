from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.draft_transaction import DraftTransaction
from app.models.vendor import Vendor
from app.schemas.draft_transaction import DraftEditableState, DraftTransactionUpdate
from app.services.audit import create_audit_log

REVIEWABLE_STATUSES = {"draft", "needs_clarification", "ready_for_review"}
DUPLICATE_RELEVANT_FIELDS = {
    "amount",
    "currency",
    "transaction_date",
    "description",
    "reference_number",
    "type",
}


@dataclass
class DraftEditActor:
    source: str
    actor_type: str
    user_id: str | None = None
    telegram_chat_id: int | None = None


def _audit_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, UUID)):
        return str(value)
    return value


async def _validate_vendor(
    db: AsyncSession, company_id, vendor_id: UUID | None
) -> None:
    if vendor_id is None:
        return
    result = await db.execute(
        select(Vendor.id).where(
            Vendor.id == vendor_id,
            Vendor.company_id == company_id,
            Vendor.is_active,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail="Invalid vendor")


async def _validate_accounts(
    db: AsyncSession,
    *,
    company_id,
    transaction_type: str,
    category_account_id: UUID | None,
    payment_account_id: UUID | None,
) -> None:
    account_ids = {
        account_id
        for account_id in (category_account_id, payment_account_id)
        if account_id is not None
    }
    if not account_ids:
        return
    result = await db.execute(
        select(Account).where(
            Account.id.in_(account_ids),
            Account.company_id == company_id,
            Account.is_active,
        )
    )
    accounts = {cast(UUID, account.id): account for account in result.scalars().all()}
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=422, detail="Invalid account selection")

    if payment_account_id is not None:
        payment = accounts[payment_account_id]
        if not payment.is_payment_account or payment.type != "asset":
            raise HTTPException(status_code=422, detail="Invalid payment account")

    if category_account_id is not None:
        category = accounts[category_account_id]
        expected_type = {
            "expense": "expense",
            "income": "revenue",
            "transfer": "asset",
        }[transaction_type]
        if category.is_payment_account or category.type != expected_type:
            raise HTTPException(
                status_code=422,
                detail="Category account does not match transaction type",
            )


async def _reevaluate_duplicate(db: AsyncSession, draft: DraftTransaction) -> None:
    draft_row: Any = draft
    if draft.duplicate_status == "exact_duplicate":
        return
    candidates = await db.execute(
        select(DraftTransaction).where(
            DraftTransaction.company_id == draft.company_id,
            DraftTransaction.id != draft.id,
            DraftTransaction.amount == draft.amount,
            DraftTransaction.currency == draft.currency,
            DraftTransaction.transaction_date == draft.transaction_date,
            DraftTransaction.status.in_(
                ["ready_for_review", "approved", "posted", "review_required"]
            ),
        )
    )
    for candidate in candidates.scalars().all():
        same_reference = bool(
            draft.reference_number
            and candidate.reference_number
            and draft.reference_number.casefold()
            == candidate.reference_number.casefold()
        )
        same_description = (
            draft.description.removeprefix("[AI] ").strip().casefold()
            == candidate.description.removeprefix("[AI] ").strip().casefold()
        )
        if same_reference or same_description:
            reason = (
                "Reference, amount, currency, and date match"
                if same_reference
                else "Description, amount, currency, and date match"
            )
            draft_row.duplicate_status = "likely_duplicate"
            draft_row.duplicate_reason = reason
            draft_row.duplicate_of_id = candidate.id
            return
    if draft.duplicate_status == "likely_duplicate":
        draft_row.duplicate_status = "unchecked"
        draft_row.duplicate_reason = (
            "Draft fields changed; duplicate review is required"
        )
        draft_row.duplicate_of_id = None
    else:
        draft_row.duplicate_status = "unique"
        draft_row.duplicate_reason = None
        draft_row.duplicate_of_id = None


async def edit_draft(
    db: AsyncSession,
    *,
    company_id,
    draft_id,
    updates: DraftTransactionUpdate,
    actor: DraftEditActor,
) -> DraftTransaction:
    result = await db.execute(
        select(DraftTransaction)
        .where(
            DraftTransaction.id == draft_id,
            DraftTransaction.company_id == company_id,
        )
        .with_for_update()
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status not in REVIEWABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Draft is no longer editable")

    supplied = updates.model_dump(exclude_unset=True)
    if not supplied:
        return draft

    merged = {
        "type": draft.type,
        "amount": draft.amount,
        "tax_amount": draft.tax_amount,
        "currency": draft.currency,
        "transaction_date": draft.transaction_date,
        "description": draft.description,
        "vendor_id": draft.vendor_id,
        "category_account_id": draft.category_account_id,
        "payment_account_id": draft.payment_account_id,
        "reference_number": draft.reference_number,
        **supplied,
    }
    validated = DraftEditableState.model_validate(merged)
    await _validate_vendor(db, company_id, validated.vendor_id)
    await _validate_accounts(
        db,
        company_id=company_id,
        transaction_type=validated.type,
        category_account_id=validated.category_account_id,
        payment_account_id=validated.payment_account_id,
    )

    before = {field: _audit_value(getattr(draft, field)) for field in supplied}
    normalized = validated.model_dump()
    changed_fields = sorted(
        field for field in supplied if before[field] != _audit_value(normalized[field])
    )
    if not changed_fields:
        return draft
    for field in supplied:
        setattr(draft, field, normalized[field])
    if DUPLICATE_RELEVANT_FIELDS.intersection(changed_fields):
        await _reevaluate_duplicate(db, draft)
    await db.flush()

    after = {field: _audit_value(getattr(draft, field)) for field in supplied}
    metadata: dict[str, Any] = {
        "source": actor.source,
        "fields_changed": changed_fields,
        "values": {
            field: {"old": before[field], "new": after[field]}
            for field in changed_fields
        },
    }
    if actor.telegram_chat_id is not None:
        metadata["telegram_chat_id"] = actor.telegram_chat_id
    await create_audit_log(
        db=db,
        company_id=str(company_id),
        user_id=actor.user_id,
        actor_type=actor.actor_type,
        action="draft.updated",
        entity_type="draft_transaction",
        entity_id=str(draft.id),
        before_data={"source": actor.source, "values": metadata["values"]},
        after_data=metadata,
    )
    return draft
