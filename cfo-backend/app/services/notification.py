from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification


async def create_notification(
    db: AsyncSession, company_id: str, user_id: str | None,
    channel: str, type_: str, title: str, message: str,
    entity_type: str | None = None, entity_id: str | None = None,
):
    notification = Notification(
        id=uuid4(), company_id=company_id, user_id=user_id,
        channel=channel, type=type_, title=title, message=message,
        entity_type=entity_type, entity_id=entity_id, status="pending",
    )
    db.add(notification)
    await db.flush()
    return notification
