from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_company_id,
    get_current_company_membership,
    get_current_user,
)
from app.models.company import CompanyMember
from app.models.draft_transaction import DraftTransaction
from app.models.inbox_item import InboxItem
from app.models.user import User
from app.schemas.draft_transaction import (
    ClarificationRequest,
    DraftTransactionResponse,
    DraftTransactionUpdate,
)
from app.services.audit import create_audit_log
from app.services.draft_editing import DraftEditActor, edit_draft
from app.services.journal import JournalError, create_journal_entry_from_draft

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
    membership: CompanyMember = Depends(get_current_company_membership),
    db: AsyncSession = Depends(get_db),
):
    membership_role = getattr(membership.role, "value", membership.role)
    if membership_role not in ("OWNER", "ADMIN", "ACCOUNTANT"):
        raise HTTPException(status_code=403, detail="Draft editing role required")
    draft = await edit_draft(
        db=db,
        company_id=company_id,
        draft_id=draft_id,
        updates=data,
        actor=DraftEditActor(
            source="dashboard",
            actor_type="user",
            user_id=str(user.id),
        ),
    )
    return DraftTransactionResponse.model_validate(draft)


@router.post("/{draft_id}/approve", response_model=DraftTransactionResponse)
async def approve_draft(
    draft_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    membership: CompanyMember = Depends(get_current_company_membership),
    db: AsyncSession = Depends(get_db),
):
    membership_role = getattr(membership.role, "value", membership.role)
    if membership_role not in ("OWNER", "ADMIN", "APPROVER"):
        raise HTTPException(status_code=403, detail="Approval role required")
    result = await db.execute(
        select(DraftTransaction).where(
            DraftTransaction.id == draft_id, DraftTransaction.company_id == company_id
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "ready_for_review":
        raise HTTPException(status_code=400, detail="Draft not ready for approval")

    draft.status = "approved"
    draft.approved_by = str(user.id)
    draft.approved_at = datetime.now(UTC).replace(tzinfo=None)
    await db.flush()

    try:
        await create_journal_entry_from_draft(db, draft)
        draft.status = "posted"
        if draft.inbox_item_id:
            inbox = await db.get(InboxItem, draft.inbox_item_id)
            if inbox and inbox.company_id == draft.company_id:
                inbox.status = "archived"
        await db.flush()
    except JournalError as e:
        draft.status = "ready_for_review"
        draft.approved_by = None
        draft.approved_at = None
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
    if draft.inbox_item_id:
        inbox = await db.get(InboxItem, draft.inbox_item_id)
        if inbox and inbox.company_id == draft.company_id:
            inbox.status = "archived"
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
