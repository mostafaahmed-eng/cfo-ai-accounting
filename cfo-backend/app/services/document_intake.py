from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage_client
from app.models.document import Document
from app.models.inbox_item import InboxItem
from app.services.document_processing import ValidatedUpload


class DocumentStorageError(RuntimeError):
    pass


@dataclass
class StoredDocumentIntake:
    document: Document
    item: InboxItem
    dispatch_processing: bool


async def store_document_intake(
    db: AsyncSession,
    *,
    company_id,
    validated: ValidatedUpload,
    original_name: str,
    source: str,
    source_reference: str | None,
    submitted_by=None,
) -> StoredDocumentIntake:
    advisory_key = int(validated.sha256_hash[:15], 16)
    await db.execute(select(func.pg_advisory_xact_lock(advisory_key)))
    existing = await db.execute(
        select(Document).where(
            Document.company_id == company_id,
            Document.sha256_hash == validated.sha256_hash,
        )
    )
    existing_doc = existing.scalars().first()
    if existing_doc:
        linked = await db.execute(
            select(InboxItem).where(
                InboxItem.id == existing_doc.inbox_item_id,
                InboxItem.company_id == company_id,
            )
        )
        existing_item = linked.scalar_one()
        dispatch_processing = False
        if existing_doc.upload_status == "failed":
            try:
                await storage_client.upload_file(
                    existing_doc.storage_key,
                    validated.content,
                    validated.mime_type,
                )
            except Exception as exc:
                raise DocumentStorageError(
                    "Document storage is temporarily unavailable"
                ) from exc
            existing_doc.upload_status = "stored"
            existing_item.status = "queued"
            existing_item.error_code = None
            existing_item.error_message = None
            await db.commit()
            dispatch_processing = True
        return StoredDocumentIntake(
            document=existing_doc,
            item=existing_item,
            dispatch_processing=dispatch_processing,
        )

    item_id = uuid4()
    document_id = uuid4()
    storage_key = (
        f"companies/{company_id}/documents/{document_id}.{validated.extension}"
    )
    safe_name = Path(original_name or f"upload.{validated.extension}").name[:255]
    item = InboxItem(
        id=item_id,
        company_id=company_id,
        source=source,
        source_reference=source_reference or str(document_id),
        content_type=(
            "document" if validated.mime_type == "application/pdf" else "image"
        ),
        status="received",
        submitted_by=submitted_by,
        content_hash=validated.sha256_hash,
        duplicate_status="unique",
    )
    document = Document(
        id=document_id,
        company_id=company_id,
        inbox_item_id=item_id,
        storage_key=storage_key,
        original_name=safe_name,
        mime_type=validated.mime_type,
        size_bytes=len(validated.content),
        sha256_hash=validated.sha256_hash,
        document_type="receipt",
        upload_status="pending",
        uploaded_by=submitted_by,
    )
    db.add_all([item, document])
    await db.flush()
    await db.commit()

    try:
        await storage_client.upload_file(
            storage_key, validated.content, validated.mime_type
        )
    except Exception as exc:
        document.upload_status = "failed"
        item.status = "failed"
        item.error_code = "storage_failed"
        item.error_message = "The document could not be stored"
        await db.commit()
        raise DocumentStorageError(
            "Document storage is temporarily unavailable"
        ) from exc

    document.upload_status = "stored"
    item.status = "queued"
    await db.commit()
    return StoredDocumentIntake(
        document=document,
        item=item,
        dispatch_processing=True,
    )
