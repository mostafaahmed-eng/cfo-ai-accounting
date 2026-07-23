import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.models.notification import Notification
from app.models.telegram import TelegramConnection
from app.tasks.telegram_responses import send_telegram_response

logger = logging.getLogger(__name__)
settings = get_settings()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL, pool_size=2, max_overflow=2)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _send(notification_id: str) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return {"status": "error", "message": "Notification not found"}

        if notification.status == "sent":
            return {"status": "ok", "message": "Already sent"}

        if notification.channel == "in_app":
            notification.status = "sent"
            await session.commit()
            return {"status": "ok", "channel": "in_app"}

        if notification.channel == "telegram":
            conn_result = await session.execute(
                select(TelegramConnection).where(
                    TelegramConnection.company_id == notification.company_id,
                    TelegramConnection.status == "active",
                )
            )
            conn = conn_result.scalar_one_or_none()
            if conn:
                send_telegram_response.delay(
                    conn.telegram_chat_id, notification.message
                )
                notification.status = "sent"
            else:
                notification.status = "failed"
                notification.error_message = "No active Telegram connection"
            await session.commit()
            return {"status": "ok", "channel": "telegram"}

        notification.status = "failed"
        notification.error_message = f"Unsupported channel: {notification.channel}"
        await session.commit()
        return {
            "status": "error",
            "message": f"Unsupported channel: {notification.channel}",
        }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification(self, notification_id: str):
    try:
        return _run_async(_send(notification_id))
    except Exception as exc:
        logger.exception("Notification send failed for %s", notification_id)
        self.retry(exc=exc)
