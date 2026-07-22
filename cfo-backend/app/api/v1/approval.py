from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.database import get_db
from app.models.approval import ApprovalRequest
from app.models.user import User
from app.schemas.approval import ApprovalResponse
from app.dependencies import get_current_user, get_current_company_id

router = APIRouter()


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.company_id == company_id,
            ApprovalRequest.status == "pending",
        ).order_by(ApprovalRequest.created_at.desc())
    )
    return [ApprovalResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id, ApprovalRequest.company_id == company_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return ApprovalResponse.model_validate(approval)
