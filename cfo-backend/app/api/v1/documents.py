from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import hashlib
import magic
from app.database import get_db
from app.config import get_settings
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse, DownloadURLResponse
from app.dependencies import get_current_user, get_current_company_id
from app.core.storage import storage_client

router = APIRouter()
settings = get_settings()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

    content = await file.read()
    mime = magic.from_buffer(content, mime=True)
    if mime not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {mime}")

    if file.content_type and file.content_type != mime:
        raise HTTPException(status_code=415, detail="MIME type mismatch")

    sha256 = hashlib.sha256(content).hexdigest()
    storage_key = f"{company_id}/{uuid4()}/{file.filename}"

    await storage_client.upload_file(storage_key, content, mime)

    doc = Document(
        id=uuid4(),
        company_id=company_id,
        storage_key=storage_key,
        original_name=file.filename,
        mime_type=mime,
        size_bytes=len(content),
        sha256_hash=sha256,
        document_type="receipt",
        upload_status="stored",
        uploaded_by=str(user.id),
    )
    db.add(doc)
    await db.flush()
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
