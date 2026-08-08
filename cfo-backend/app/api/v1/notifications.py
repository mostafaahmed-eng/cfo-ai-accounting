from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.schemas.pagination import PageParams, get_page_params

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
):
    filters = (
        Notification.company_id == company_id,
        Notification.user_id == str(user.id),
    )
    total = await db.scalar(
        select(func.count()).select_from(Notification).where(*filters)
    )
    result = await db.execute(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
    )
    response.headers["X-Total-Count"] = str(total)
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
        notification.read_at = datetime.now(UTC).replace(tzinfo=None)
        await db.flush()
    return {"message": "Marked as read"}
