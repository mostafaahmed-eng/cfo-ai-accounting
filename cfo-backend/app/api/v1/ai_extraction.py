from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.limiter import ai_company_key, limiter
from app.models.ai_extraction import AIExtraction
from app.models.inbox_item import InboxItem
from app.models.user import User
from app.schemas.ai_extraction import AIExtractionResponse
from app.schemas.pagination import PageParams, get_page_params
from app.tasks.ai_extraction import run_ai_extraction

router = APIRouter()
settings = get_settings()


async def _dispatch_extraction(
    db: AsyncSession, company_id: str, inbox_item_id: str
) -> dict:
    result = await db.execute(
        select(InboxItem).where(
            InboxItem.id == inbox_item_id, InboxItem.company_id == company_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    if not item.original_text:
        raise HTTPException(status_code=400, detail="No text content to extract")
    if item.status == "failed":
        item.status = "queued"
        item.error_code = None
        item.error_message = None
    await db.commit()
    run_ai_extraction.delay(str(item.id))
    return {"status": "dispatched", "inbox_item_id": str(item.id)}


@router.post("/{inbox_item_id}/extract")
@limiter.shared_limit(settings.RATE_LIMIT_AI, "ai-extraction", key_func=ai_company_key)
async def trigger_extraction(
    request: Request,
    response: Response,
    inbox_item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await _dispatch_extraction(db, company_id, inbox_item_id)


@router.post("/{inbox_item_id}/extract-async")
@limiter.shared_limit(settings.RATE_LIMIT_AI, "ai-extraction", key_func=ai_company_key)
async def trigger_extraction_async(
    request: Request,
    response: Response,
    inbox_item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await _dispatch_extraction(db, company_id, inbox_item_id)


@router.get("/{inbox_item_id}", response_model=list[AIExtractionResponse])
async def list_extractions(
    inbox_item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
):
    filters = (
        AIExtraction.inbox_item_id == inbox_item_id,
        AIExtraction.company_id == company_id,
    )
    total = await db.scalar(
        select(func.count()).select_from(AIExtraction).where(*filters)
    )
    result = await db.execute(
        select(AIExtraction)
        .where(*filters)
        .order_by(AIExtraction.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
    )
    response.headers["X-Total-Count"] = str(total)
    return [AIExtractionResponse.model_validate(e) for e in result.scalars().all()]
