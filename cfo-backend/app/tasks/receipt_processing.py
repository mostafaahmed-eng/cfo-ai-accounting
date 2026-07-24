import asyncio
import hashlib

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.storage import storage_client
from app.models.document import Document
from app.models.inbox_item import InboxItem
from app.services.document_processing import (
    DocumentProviderError,
    _validate_file_structure,
    extract_text_from_document,
)
from app.services.intake import normalized_text_hash
from app.tasks.ai_extraction import run_ai_extraction
from app.tasks.celery_app import celery_app

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


async def _fail_item(inbox_item_id: str, code: str, message: str) -> None:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(InboxItem).where(InboxItem.id == inbox_item_id).with_for_update()
        )
        item = result.scalar_one_or_none()
        if item:
            item.status = "failed"
            item.error_code = code
            item.error_message = message
            await session.commit()


async def _process(inbox_item_id: str, document_id: str) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(InboxItem, Document)
            .join(Document, Document.inbox_item_id == InboxItem.id)
            .where(
                InboxItem.id == inbox_item_id,
                Document.id == document_id,
                Document.company_id == InboxItem.company_id,
            )
        )
        row = result.first()
        if not row:
            return {"status": "error", "message": "Document intake not found"}
        item, document = row
        if item.original_text and item.status in {
            "queued",
            "processing",
            "review_required",
            "completed",
        }:
            if item.status == "queued":
                run_ai_extraction.delay(str(item.id))
            return {"status": "already_processed", "inbox_item_id": str(item.id)}
        item.status = "processing"
        item.processing_attempts = (item.processing_attempts or 0) + 1
        await session.commit()
        storage_key = document.storage_key
        expected_hash = document.sha256_hash
        mime_type = document.mime_type
        filename = document.original_name

    try:
        content = await storage_client.download_file(storage_key)
        if len(content) > settings.MAX_UPLOAD_SIZE:
            await _fail_item(
                inbox_item_id, "file_too_large", "Stored file exceeds upload limit"
            )
            return {"status": "failed", "reason": "file_too_large"}
        if hashlib.sha256(content).hexdigest() != expected_hash:
            await _fail_item(
                inbox_item_id,
                "file_integrity",
                "Stored file failed integrity validation",
            )
            return {"status": "failed", "reason": "file_integrity"}
        _validate_file_structure(content, mime_type)
        ocr = await extract_text_from_document(content, mime_type, filename)
    except (httpx.TimeoutException, httpx.TransportError):
        await _fail_item(
            inbox_item_id,
            "provider_temporarily_unavailable",
            "The document provider is temporarily unavailable",
        )
        raise
    except DocumentProviderError:
        await _fail_item(
            inbox_item_id, "ocr_failed", "No readable text could be extracted"
        )
        return {"status": "failed", "reason": "ocr_failed"}
    except Exception:
        await _fail_item(
            inbox_item_id, "document_processing_failed", "Document processing failed"
        )
        return {"status": "failed", "reason": "document_processing_failed"}

    async with session_factory() as session:
        locked = await session.execute(
            select(InboxItem).where(InboxItem.id == inbox_item_id).with_for_update()
        )
        item = locked.scalar_one()
        item.original_text = ocr["text"]
        item.content_hash = normalized_text_hash(ocr["text"])
        item.status = "queued"
        item.error_code = None
        item.error_message = None
        await session.commit()
    run_ai_extraction.delay(inbox_item_id)
    return {"status": "queued", "inbox_item_id": inbox_item_id}


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(httpx.TimeoutException, httpx.TransportError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def process_receipt(self, inbox_item_id: str, document_id: str):
    return _run_async(_process(inbox_item_id, document_id))
