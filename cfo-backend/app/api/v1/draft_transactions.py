from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.database import get_db
from app.models.draft_transaction import DraftTransaction
from app.models.user import User
from app.schemas.draft_transaction import (
    DraftTransactionUpdate,
    DraftTransactionResponse,
    ClarificationRequest,
)
from app.dependencies import get_current_user, get_current_company_id
from app.services.journal import create_journal_entry_from_draft, JournalError
from app.services.audit import create_audit_log

router = APIRouter()


@router.get("", response_model=list[DraftTransactionResponse])
async def list_drafts(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DraftTransaction)
        .where(DraftTransaction.company_id == company_id)
        .order_by(DraftTransaction.created_at.desc())
    )
    return [DraftTransactionResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/{draft_id}", response_model=DraftTransactionResponse)
async def get_draft(
    draft_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DraftTransaction).where(
            DraftTransaction.id == draft_id, DraftTransaction.company_id == company_id
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return DraftTransactionResponse.model_validate(draft)


@router.patch("/{draft_id}", response_model=DraftTransactionResponse)
async def update_draft(
    draft_id: str,
    data: DraftTransactionUpdate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DraftTransaction).where(
            DraftTransaction.id == draft_id, DraftTransaction.company_id == company_id
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status in ("posted", "approved"):
        raise HTTPException(
            status_code=400, detail="Cannot edit posted or approved transaction"
        )
    before = {"status": draft.status, "amount": float(draft.amount)}
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(draft, field, value)
    draft.status = "ready_for_review"
    await db.flush()
    await create_audit_log(
        db=db,
        company_id=str(company_id),
        user_id=str(user.id),
        actor_type="user",
        action="draft.updated",
        entity_type="draft_transaction",
        entity_id=str(draft.id),
        before_data=before,
        after_data={"status": "ready_for_review", "amount": float(draft.amount)},
    )
    return DraftTransactionResponse.model_validate(draft)


@router.post("/{draft_id}/approve", response_model=DraftTransactionResponse)
async def approve_draft(
    draft_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DraftTransaction).where(
            DraftTransaction.id == draft_id, DraftTransaction.company_id == company_id
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status not in ("ready_for_review", "needs_clarification"):
        raise HTTPException(status_code=400, detail="Draft not ready for approval")

    draft.status = "approved"
    draft.approved_by = str(user.id)
    draft.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()

    try:
        await create_journal_entry_from_draft(db, draft)
        draft.status = "posted"
        await db.flush()
    except JournalError as e:
        draft.status = "approved"
        await db.flush()
        raise HTTPException(status_code=400, detail=e.detail)

    await create_audit_log(
        db=db,
        company_id=str(company_id),
        user_id=str(user.id),
        actor_type="user",
        action="draft.approved",
        entity_type="draft_transaction",
        entity_id=str(draft.id),
        before_data={"status": "ready_for_review"},
        after_data={"status": "posted", "amount": float(draft.amount)},
    )

    return DraftTransactionResponse.model_validate(draft)


@router.post("/{draft_id}/reject", response_model=DraftTransactionResponse)
async def reject_draft(
    draft_id: str,
    data: ClarificationRequest | None = None,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DraftTransaction).where(
            DraftTransaction.id == draft_id, DraftTransaction.company_id == company_id
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    old_status = draft.status
    draft.status = "rejected"
    await db.flush()
    await create_audit_log(
        db=db,
        company_id=str(company_id),
        user_id=str(user.id),
        actor_type="user",
        action="draft.rejected",
        entity_type="draft_transaction",
        entity_id=str(draft.id),
        before_data={"status": old_status},
        after_data={"status": "rejected"},
    )
    return DraftTransactionResponse.model_validate(draft)


@router.post(
    "/{draft_id}/request-clarification", response_model=DraftTransactionResponse
)
async def request_clarification(
    draft_id: str,
    data: ClarificationRequest,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DraftTransaction).where(
            DraftTransaction.id == draft_id, DraftTransaction.company_id == company_id
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.status = "needs_clarification"
    await db.flush()
    return DraftTransactionResponse.model_validate(draft)
