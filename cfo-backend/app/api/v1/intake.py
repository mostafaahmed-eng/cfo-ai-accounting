from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from app.database import get_db
from app.models.inbox_item import InboxItem
from app.models.user import User
from app.schemas.inbox_item import TextInput, InboxItemResponse
from app.dependencies import get_current_user, get_current_company_id
from app.core.text_processing import detect_language

router = APIRouter()


@router.post("/text", response_model=InboxItemResponse)
async def submit_text(
    data: TextInput,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    lang = data.language or detect_language(data.text)
    item = InboxItem(
        id=uuid4(), company_id=company_id, source="web_text", content_type="text",
        original_text=data.text, detected_language=lang, status="received",
        submitted_by=str(user.id), idempotency_key=data.idempotency_key,
    )
    db.add(item)
    await db.flush()
    return InboxItemResponse.model_validate(item)


@router.post("/receipt", response_model=InboxItemResponse)
async def submit_receipt(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    item = InboxItem(
        id=uuid4(), company_id=company_id, source="web_receipt", content_type="image",
        status="received", submitted_by=str(user.id),
    )
    db.add(item)
    await db.flush()
    return InboxItemResponse.model_validate(item)


@router.get("/{item_id}", response_model=InboxItemResponse)
async def get_inbox_item(
    item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InboxItem).where(InboxItem.id == item_id, InboxItem.company_id == company_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return InboxItemResponse.model_validate(item)


@router.post("/{item_id}/retry", response_model=InboxItemResponse)
async def retry_inbox_item(
    item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InboxItem).where(InboxItem.id == item_id, InboxItem.company_id == company_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    item.status = "received"
    item.error_code = None
    item.error_message = None
    await db.flush()
    return InboxItemResponse.model_validate(item)
