from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.dependencies import get_current_user, get_current_company_id

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(
            Notification.company_id == company_id,
            Notification.user_id == str(user.id),
        )
        .order_by(Notification.created_at.desc())
    )
    return [NotificationResponse.model_validate(n) for n in result.scalars().all()]


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.company_id == company_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification:
        notification.status = "read"
        notification.read_at = datetime.utcnow()
        await db.flush()
    return {"message": "Marked as read"}
