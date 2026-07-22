from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from app.database import get_db
from app.models.ai_extraction import AIExtraction
from app.models.inbox_item import InboxItem
from app.models.user import User
from app.schemas.ai_extraction import AIExtractionResponse
from app.dependencies import get_current_user, get_current_company_id
from app.config import get_settings
from app.services.ai_extraction import extract_from_text
from app.tasks.ai_extraction import run_ai_extraction

router = APIRouter()


@router.post("/{inbox_item_id}/extract", response_model=AIExtractionResponse)
async def trigger_extraction(
    inbox_item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InboxItem).where(InboxItem.id == inbox_item_id, InboxItem.company_id == company_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    if not item.original_text:
        raise HTTPException(status_code=400, detail="No text content to extract")

    extraction_result = await extract_from_text(item.original_text, item.detected_language or "en")

    from app.schemas.ai_extraction import ExtractionResult
    validated = None
    try:
        validated = ExtractionResult.model_validate(extraction_result.get("extracted", {}))
    except Exception:
        pass

    settings = get_settings()
    extraction = AIExtraction(
        id=uuid4(), company_id=company_id, inbox_item_id=inbox_item_id,
        provider="openrouter", model=settings.OPENROUTER_MODEL, prompt_version="v1.0",
        request_payload={"text": item.original_text, "language": item.detected_language},
        raw_response=extraction_result.get("raw_response", {}),
        validated_result=validated.model_dump(mode="json") if validated else extraction_result.get("extracted"),
        status="succeeded" if validated else "partial",
        input_tokens=extraction_result.get("input_tokens"),
        output_tokens=extraction_result.get("output_tokens"),
        estimated_cost=extraction_result.get("estimated_cost"),
        processing_ms=extraction_result.get("processing_ms"),
    )
    db.add(extraction)

    item.status = "extracted"
    await db.flush()
    return AIExtractionResponse.model_validate(extraction)


@router.post("/{inbox_item_id}/extract-async")
async def trigger_extraction_async(
    inbox_item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InboxItem).where(InboxItem.id == inbox_item_id, InboxItem.company_id == company_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    if not item.original_text:
        raise HTTPException(status_code=400, detail="No text content to extract")

    run_ai_extraction.delay(inbox_item_id)
    return {"status": "dispatched", "inbox_item_id": inbox_item_id}


@router.get("/{inbox_item_id}", response_model=list[AIExtractionResponse])
async def list_extractions(
    inbox_item_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIExtraction).where(
            AIExtraction.inbox_item_id == inbox_item_id,
            AIExtraction.company_id == company_id,
        ).order_by(AIExtraction.created_at.desc())
    )
    return [AIExtractionResponse.model_validate(e) for e in result.scalars().all()]
