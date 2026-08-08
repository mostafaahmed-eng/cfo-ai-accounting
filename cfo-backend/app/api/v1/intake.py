from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.text_processing import detect_language
from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.limiter import ai_company_key, limiter
from app.models.inbox_item import InboxItem
from app.models.user import User
from app.schemas.inbox_item import InboxItemResponse, TextInput
from app.schemas.pagination import PageParams, get_page_params
from app.services.intake import create_text_inbox
from app.tasks.ai_extraction import run_ai_extraction

router = APIRouter()
settings = get_settings()


@router.get("", response_model=list[InboxItemResponse])
async def list_inbox_items(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
    status: str | None = None,
):
    filters = [InboxItem.company_id == company_id]
    if status:
        filters.append(InboxItem.status == status)
    else:
        filters.append(InboxItem.status != "archived")
    total = await db.scalar(select(func.count()).select_from(InboxItem).where(*filters))
    query = (
        select(InboxItem)
        .where(*filters)
        .order_by(InboxItem.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
    )
    result = await db.execute(query)
    response.headers["X-Total-Count"] = str(total)
    return [InboxItemResponse.model_validate(i) for i in result.scalars().all()]


@router.post("/text", response_model=InboxItemResponse)
@limiter.shared_limit(settings.RATE_LIMIT_AI, "ai-extraction", key_func=ai_company_key)
async def submit_text(
    request: Request,
    response: Response,
    data: TextInput,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    lang = data.language or detect_language(data.text)
    creation = await create_text_inbox(
        db,
        company_id=company_id,
        text=data.text,
        language=lang,
        source="web_text",
        submitted_by=user.id,
        idempotency_key=data.idempotency_key,
    )
    await db.commit()
    if creation.created:
        run_ai_extraction.delay(str(creation.item.id))
    return InboxItemResponse.model_validate(creation.item)


@router.post("/receipt", response_model=InboxItemResponse)
async def submit_receipt(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(
        status_code=400,
        detail="Upload the receipt file through /documents/upload",
    )


@router.get("/{item_id}", response_model=InboxItemResponse)
async def get_inbox_item(
    item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InboxItem).where(
            InboxItem.id == item_id, InboxItem.company_id == company_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return InboxItemResponse.model_validate(item)


@router.post("/{item_id}/retry", response_model=InboxItemResponse)
@limiter.shared_limit(settings.RATE_LIMIT_AI, "ai-extraction", key_func=ai_company_key)
async def retry_inbox_item(
    request: Request,
    response: Response,
    item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InboxItem).where(
            InboxItem.id == item_id, InboxItem.company_id == company_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    if item.status in {"completed", "extracted", "review_required"}:
        return InboxItemResponse.model_validate(item)
    item.status = "queued"
    item.error_code = None
    item.error_message = None
    await db.flush()
    await db.commit()
    run_ai_extraction.delay(str(item.id))
    return InboxItemResponse.model_validate(item)
