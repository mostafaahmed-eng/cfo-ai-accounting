import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.ai_extraction import AIExtraction
from app.models.draft_transaction import DraftTransaction
from app.models.inbox_item import InboxItem
from app.models.telegram import TelegramConnection
from app.schemas.ai_extraction import ExtractionResult
from app.services.ai_extraction import EXTRACTION_PROMPT_VERSION, extract_from_text
from app.tasks.celery_app import celery_app
from app.tasks.telegram_responses import send_telegram_response

logger = logging.getLogger(__name__)
settings = get_settings()


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL, pool_size=2, max_overflow=2)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _claim_item(session: AsyncSession, inbox_item_id: str):
    result = await session.execute(
        select(InboxItem).where(InboxItem.id == inbox_item_id).with_for_update()
    )
    item = result.scalar_one_or_none()
    if item is None:
        return None, {"status": "error", "message": "Inbox item not found"}
    if item.status in {"completed", "extracted", "review_required"}:
        return None, {"status": "already_processed", "inbox_item_id": str(item.id)}
    if item.status == "processing":
        return None, {"status": "already_processing", "inbox_item_id": str(item.id)}
    if not item.original_text:
        item.status = "failed"
        item.error_code = "no_text"
        item.error_message = "No readable text is available for extraction"
        return None, {"status": "failed", "reason": "no_text"}

    item.status = "processing"
    item.processing_attempts = (item.processing_attempts or 0) + 1
    item.error_code = None
    item.error_message = None
    await session.commit()
    return item, None


async def _record_transient_failure(inbox_item_id: str) -> None:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(InboxItem).where(InboxItem.id == inbox_item_id).with_for_update()
        )
        item = result.scalar_one_or_none()
        if item and item.status == "processing":
            item.status = "queued"
            item.error_code = "provider_temporarily_unavailable"
            item.error_message = "The extraction provider is temporarily unavailable"
            await session.commit()


async def _find_duplicate(
    session: AsyncSession,
    item: InboxItem,
    extracted: ExtractionResult,
):
    exact = await session.execute(
        select(InboxItem).where(
            InboxItem.company_id == item.company_id,
            InboxItem.id != item.id,
            InboxItem.content_hash == item.content_hash,
            InboxItem.status.in_(["review_required", "completed", "extracted"]),
        )
    )
    exact_item = exact.scalars().first()
    if exact_item:
        return "exact_duplicate", "Normalized content matches an existing item", None

    candidates = await session.execute(
        select(DraftTransaction).where(
            DraftTransaction.company_id == item.company_id,
            DraftTransaction.inbox_item_id != item.id,
            DraftTransaction.amount == extracted.amount,
            DraftTransaction.currency == extracted.currency,
            DraftTransaction.transaction_date == extracted.transaction_date,
            DraftTransaction.status.in_(
                ["ready_for_review", "approved", "posted", "review_required"]
            ),
        )
    )
    for candidate in candidates.scalars().all():
        same_reference = bool(
            extracted.reference_number
            and candidate.reference_number
            and extracted.reference_number.strip().casefold()
            == candidate.reference_number.strip().casefold()
        )
        same_description = (
            extracted.description.strip().casefold()
            == candidate.description.removeprefix("[AI] ").strip().casefold()
        )
        if same_reference or same_description:
            reason = (
                "Reference, amount, currency, and date match"
                if same_reference
                else "Description, amount, currency, and date match"
            )
            return "likely_duplicate", reason, candidate
    return "unique", None, None


async def _finalize_extraction(
    session: AsyncSession,
    item: InboxItem,
    extraction_result: dict,
) -> dict:
    locked = await session.execute(
        select(InboxItem).where(InboxItem.id == item.id).with_for_update()
    )
    item = locked.scalar_one()

    existing_draft = await session.execute(
        select(DraftTransaction).where(
            DraftTransaction.inbox_item_id == item.id,
            DraftTransaction.company_id == item.company_id,
        )
    )
    draft = existing_draft.scalars().first()
    is_telegram_correction = bool(
        draft
        and item.source == "telegram"
        and draft.status == "needs_clarification"
        and item.status == "processing"
    )
    if draft and not is_telegram_correction:
        item.status = "review_required"
        await session.commit()
        return {
            "status": "already_processed",
            "draft_id": str(draft.id),
            "inbox_item_id": str(item.id),
        }

    try:
        extracted = ExtractionResult.model_validate(extraction_result.get("extracted"))
        if extracted.amount <= 0 or not extracted.currency.strip():
            raise ValueError("Required financial fields are missing")
    except Exception:
        extraction = AIExtraction(
            id=uuid4(),
            company_id=item.company_id,
            inbox_item_id=item.id,
            provider="openrouter",
            model=settings.OPENROUTER_MODEL,
            prompt_version=EXTRACTION_PROMPT_VERSION,
            request_payload={
                "content_hash": item.content_hash,
                "language": item.detected_language,
            },
            raw_response={"response_received": True},
            validated_result=None,
            status="invalid",
            input_tokens=extraction_result.get("input_tokens"),
            output_tokens=extraction_result.get("output_tokens"),
            estimated_cost=extraction_result.get("estimated_cost"),
            processing_ms=extraction_result.get("processing_ms"),
            error_message="Provider output did not contain valid required financial fields",
        )
        session.add(extraction)
        item.status = "failed"
        item.error_code = "invalid_extraction"
        item.error_message = "Could not extract the required financial fields"
        await session.commit()
        return {"status": "failed", "reason": "invalid_extraction"}

    extraction = AIExtraction(
        id=uuid4(),
        company_id=item.company_id,
        inbox_item_id=item.id,
        provider="openrouter",
        model=settings.OPENROUTER_MODEL,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        request_payload={
            "content_hash": item.content_hash,
            "language": item.detected_language,
        },
        raw_response={"response_received": True},
        validated_result=extracted.model_dump(mode="json"),
        status="succeeded",
        input_tokens=extraction_result.get("input_tokens"),
        output_tokens=extraction_result.get("output_tokens"),
        estimated_cost=extraction_result.get("estimated_cost"),
        processing_ms=extraction_result.get("processing_ms"),
    )
    session.add(extraction)

    duplicate_status, duplicate_reason, duplicate_of = await _find_duplicate(
        session, item, extracted
    )
    vendor_name = extracted.vendor.name or ""
    description = extracted.description.strip()
    if vendor_name:
        description = f"{description} — {vendor_name}"
    draft_status = (
        "needs_clarification" if item.source == "telegram" else "ready_for_review"
    )
    if draft:
        draft.type = extracted.transaction_type
        draft.amount = extracted.amount
        draft.tax_amount = extracted.tax_amount or 0
        draft.currency = extracted.currency.upper()
        draft.transaction_date = extracted.transaction_date
        draft.description = f"[AI] {description}"
        draft.reference_number = extracted.reference_number
        draft.status = draft_status
        draft.ai_confidence = extracted.confidence.overall
        draft.duplicate_status = duplicate_status
        draft.duplicate_reason = duplicate_reason
        draft.duplicate_of_id = duplicate_of.id if duplicate_of else None
    else:
        draft = DraftTransaction(
            id=uuid4(),
            company_id=item.company_id,
            inbox_item_id=item.id,
            type=extracted.transaction_type,
            amount=extracted.amount,
            tax_amount=extracted.tax_amount or 0,
            currency=extracted.currency.upper(),
            transaction_date=extracted.transaction_date,
            description=f"[AI] {description}",
            category_account_id=None,
            payment_account_id=None,
            reference_number=extracted.reference_number,
            status=draft_status,
            ai_confidence=extracted.confidence.overall,
            duplicate_status=duplicate_status,
            duplicate_reason=duplicate_reason,
            duplicate_of_id=duplicate_of.id if duplicate_of else None,
        )
        session.add(draft)
    item.status = "review_required"
    item.duplicate_status = duplicate_status
    item.duplicate_reason = duplicate_reason
    item.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    return {
        "status": "review_required",
        "extraction_id": str(extraction.id),
        "draft_id": str(draft.id),
        "duplicate_status": duplicate_status,
        "category_hint": extracted.category_hint,
    }


async def _process_extraction(inbox_item_id: str) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        item, terminal = await _claim_item(session, inbox_item_id)
        if terminal:
            return terminal
        assert item is not None
        text = item.original_text
        language = item.detected_language or "en"

    try:
        extraction_result = await extract_from_text(text, language)
    except (httpx.TimeoutException, httpx.TransportError):
        await _record_transient_failure(inbox_item_id)
        raise
    except Exception:
        async with session_factory() as session:
            locked = await session.execute(
                select(InboxItem).where(InboxItem.id == inbox_item_id).with_for_update()
            )
            failed_item = locked.scalar_one_or_none()
            if failed_item:
                failed_item.status = "failed"
                failed_item.error_code = "provider_failure"
                failed_item.error_message = (
                    "Extraction provider returned an invalid response"
                )
                await session.commit()
        return {"status": "failed", "reason": "provider_failure"}

    async with session_factory() as session:
        result = await _finalize_extraction(session, item, extraction_result)
        if result.get("draft_id"):
            chat_id = await _get_telegram_chat_id(session, item.company_id)
            if chat_id and item.source == "telegram":
                draft_result = await session.execute(
                    select(DraftTransaction).where(
                        DraftTransaction.id == result["draft_id"],
                        DraftTransaction.company_id == item.company_id,
                    )
                )
                draft = draft_result.scalar_one()
                category_hint = result.get("category_hint") or "Not identified"
                send_telegram_response.delay(
                    chat_id,
                    "Here’s what I extracted:\n"
                    f"Amount: {draft.currency} {draft.amount}\n"
                    f"Description: {draft.description.removeprefix('[AI] ')}\n"
                    f"Category hint: {category_hint}\n"
                    f"Date: {draft.transaction_date}\n\n"
                    "Does this look correct?",
                    {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "✅ Correct",
                                    "callback_data": f"confirm:{draft.id}",
                                }
                            ],
                            [
                                {
                                    "text": "✏️ Not quite, let me fix it",
                                    "callback_data": f"correct:{draft.id}",
                                }
                            ],
                        ]
                    },
                )
        return result


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(httpx.TimeoutException, httpx.TransportError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def run_ai_extraction(self, inbox_item_id: str):
    return _run_async(_process_extraction(inbox_item_id))


async def _get_telegram_chat_id(session, company_id) -> int | None:
    result = await session.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status == "active",
        )
    )
    connection = result.scalar_one_or_none()
    return connection.telegram_chat_id if connection else None
