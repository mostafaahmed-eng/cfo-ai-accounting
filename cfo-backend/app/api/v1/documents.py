from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage_client
from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse, DownloadURLResponse
from app.services.document_intake import (
    DocumentStorageError,
    store_document_intake,
)
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

    try:
        stored = await store_document_intake(
            db,
            company_id=company_id,
            validated=validated,
            original_name=file.filename or f"upload.{validated.extension}",
            source="web_receipt",
            source_reference=None,
            submitted_by=user.id,
        )
    except DocumentStorageError:
        raise HTTPException(
            status_code=503,
            detail="Document storage is temporarily unavailable",
        )

    if stored.dispatch_processing:
        process_receipt.delay(str(stored.item.id), str(stored.document.id))
    return DocumentResponse.model_validate(stored.document)


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
