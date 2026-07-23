import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.models.inbox_item import InboxItem
from app.models.document import Document
from app.tasks.ai_extraction import run_ai_extraction

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


async def _process(inbox_item_id: str, document_id: str) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        item_result = await session.execute(
            select(InboxItem).where(InboxItem.id == inbox_item_id)
        )
        item = item_result.scalar_one_or_none()
        if not item:
            return {"status": "error", "message": "Inbox item not found"}

        doc_result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = doc_result.scalar_one_or_none()
        if not doc:
            return {"status": "error", "message": "Document not found"}

        allowed = [
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
        ]
        if doc.mime_type not in allowed:
            item.status = "failed"
            item.error_code = "unsupported_mime"
            item.error_message = f"Unsupported file type: {doc.mime_type}"
            await session.commit()
            return {"status": "error", "message": f"Unsupported: {doc.mime_type}"}

        item.document_id = doc.id
        item.status = "processing"
        await session.commit()

        run_ai_extraction.delay(inbox_item_id)

        return {"status": "ok", "inbox_item_id": inbox_item_id, "queued": True}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_receipt(self, inbox_item_id: str, document_id: str):
    try:
        return _run_async(_process(inbox_item_id, document_id))
    except Exception as exc:
        logger.exception("Receipt processing failed for %s", inbox_item_id)
        self.retry(exc=exc)
