from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.models.document import Document
from app.models.inbox_item import InboxItem
from app.models.user import User
from app.schemas.document import DocumentResponse, DownloadURLResponse
from app.dependencies import get_current_user, get_current_company_id
from app.core.storage import storage_client
from app.services.document_processing import (
    DocumentValidationError,
    validate_upload,
)
from app.tasks.receipt_processing import process_receipt

router = APIRouter()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        validated = await validate_upload(file)
    except DocumentValidationError as exc:
        status_code = 413 if exc.code == "file_too_large" else 415
        if exc.code in {
            "empty_file",
            "malformed_pdf",
            "malformed_image",
            "encrypted_pdf",
            "pdf_page_limit",
        }:
            status_code = 422
        raise HTTPException(status_code=status_code, detail=exc.detail)

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
        if existing_doc.upload_status == "failed":
            linked = await db.execute(
                select(InboxItem).where(
                    InboxItem.id == existing_doc.inbox_item_id,
                    InboxItem.company_id == company_id,
                )
            )
            existing_item = linked.scalar_one()
            try:
                await storage_client.upload_file(
                    existing_doc.storage_key,
                    validated.content,
                    validated.mime_type,
                )
            except Exception:
                raise HTTPException(
                    status_code=503,
                    detail="Document storage is temporarily unavailable",
                )
            existing_doc.upload_status = "stored"
            existing_item.status = "queued"
            existing_item.error_code = None
            existing_item.error_message = None
            await db.commit()
            process_receipt.delay(str(existing_item.id), str(existing_doc.id))
        return DocumentResponse.model_validate(existing_doc)

    item_id = uuid4()
    document_id = uuid4()
    storage_key = (
        f"companies/{company_id}/documents/{document_id}.{validated.extension}"
    )
    original_name = Path(file.filename or f"upload.{validated.extension}").name[:255]

    doc = Document(
        id=document_id,
        company_id=company_id,
        inbox_item_id=item_id,
        storage_key=storage_key,
        original_name=original_name,
        mime_type=validated.mime_type,
        size_bytes=len(validated.content),
        sha256_hash=validated.sha256_hash,
        document_type="receipt",
        upload_status="pending",
        uploaded_by=str(user.id),
    )
    item = InboxItem(
        id=item_id,
        company_id=company_id,
        source="web_receipt",
        source_reference=str(document_id),
        content_type=(
            "document" if validated.mime_type == "application/pdf" else "image"
        ),
        status="received",
        submitted_by=user.id,
        content_hash=validated.sha256_hash,
        duplicate_status="unique",
    )
    db.add_all([item, doc])
    await db.flush()
    await db.commit()

    try:
        await storage_client.upload_file(
            storage_key, validated.content, validated.mime_type
        )
    except Exception:
        doc.upload_status = "failed"
        item.status = "failed"
        item.error_code = "storage_failed"
        item.error_message = "The document could not be stored"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Document storage is temporarily unavailable",
        )

    doc.upload_status = "stored"
    item.status = "queued"
    await db.commit()
    process_receipt.delay(str(item.id), str(doc.id))
    return DocumentResponse.model_validate(doc)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.get("/{doc_id}/download-url", response_model=DownloadURLResponse)
async def get_download_url(
    doc_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    url = await storage_client.get_signed_url(doc.storage_key, expires_in=3600)
    return DownloadURLResponse(
        download_url=url,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
    )


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await storage_client.delete_file(doc.storage_key)
    await db.delete(doc)
    return {"message": "Document deleted"}
