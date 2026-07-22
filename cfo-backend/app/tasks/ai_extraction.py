import asyncio
import logging
from uuid import uuid4
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.services.ai_extraction import extract_from_text, EXTRACTION_PROMPT_VERSION
from app.models.ai_extraction import AIExtraction
from app.models.inbox_item import InboxItem
from app.models.draft_transaction import DraftTransaction
from app.models.account import Account
from app.models.telegram import TelegramConnection
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


async def _process_extraction(inbox_item_id: str) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        item = await session.execute(
            select(InboxItem).where(InboxItem.id == inbox_item_id)
        )
        item = item.scalar_one_or_none()

        if not item:
            logger.error("InboxItem %s not found", inbox_item_id)
            return {"status": "error", "message": "Inbox item not found"}

        text = item.original_text
        if not text:
            item.status = "error"
            item.error_code = "no_text"
            item.error_message = "No text content to extract"
            await session.commit()
            return {"status": "error", "message": "No text content"}

        extraction_result = await extract_from_text(
            text, item.detected_language or "en"
        )

        ai_extraction = AIExtraction(
            id=uuid4(),
            company_id=item.company_id,
            inbox_item_id=item.id,
            provider="openrouter",
            model=settings.OPENROUTER_MODEL,
            prompt_version=EXTRACTION_PROMPT_VERSION,
            request_payload={"text": text, "language": item.detected_language},
            raw_response=extraction_result.get("raw_response", {}),
            validated_result=extraction_result.get("extracted"),
            status="succeeded" if extraction_result.get("validated") else "partial",
            input_tokens=extraction_result.get("input_tokens"),
            output_tokens=extraction_result.get("output_tokens"),
            estimated_cost=extraction_result.get("estimated_cost"),
            processing_ms=extraction_result.get("processing_ms"),
        )
        session.add(ai_extraction)

        extracted = extraction_result.get("extracted", {})
        draft_id = None
        if extracted and extracted.get("amount"):
            draft = await _create_draft_from_extraction(session, item, extracted)
            if draft:
                draft_id = str(draft.id)
            item.status = "extracted"
        else:
            item.status = "error"
            item.error_code = "extraction_failed"
            item.error_message = extraction_result.get(
                "validation_error", "Extraction returned no data"
            )

        await session.commit()

        extracted_data = extraction_result.get("extracted", {})
        chat_id = await _get_telegram_chat_id(session, item.company_id)
        if chat_id:
            _send_result_to_telegram(chat_id, item, extracted_data, draft_id)

        return {
            "status": "ok" if extracted and extracted.get("amount") else "error",
            "extraction_id": str(ai_extraction.id),
            "draft_id": draft_id,
            "validated": extraction_result.get("validated", False),
        }


async def _create_draft_from_extraction(session, item: InboxItem, extracted: dict):
    amount = extracted.get("amount", 0)
    if not amount or amount <= 0:
        return None

    txn_type = extracted.get("transaction_type", "expense")
    if txn_type not in ("expense", "income", "transfer"):
        txn_type = "expense"

    txn_date_str = extracted.get("transaction_date")
    try:
        txn_date = date.fromisoformat(txn_date_str) if txn_date_str else date.today()
    except ValueError:
        txn_date = date.today()

    currency = extracted.get("currency", "USD")
    description = extracted.get("description", "AI extracted transaction")
    vendor_name = extracted.get("vendor", {}).get("name", "")
    tax_amount = extracted.get("tax_amount", 0) or 0
    confidence = extracted.get("confidence", {}).get("overall", 0) or 0

    accounts = await session.execute(
        select(Account).where(Account.company_id == item.company_id)
    )
    accounts = accounts.scalars().all()

    category_account_id = None
    payment_account_id = None
    for acct in accounts:
        if acct.type == "asset" and not payment_account_id:
            payment_account_id = acct.id
        elif acct.type == "expense" and not category_account_id:
            category_account_id = acct.id

    draft = DraftTransaction(
        id=uuid4(),
        company_id=item.company_id,
        inbox_item_id=item.id,
        type=txn_type,
        amount=amount,
        tax_amount=tax_amount,
        currency=currency,
        transaction_date=txn_date,
        description=f"[AI] {description}"
        + (f" — {vendor_name}" if vendor_name else ""),
        category_account_id=category_account_id,
        payment_account_id=payment_account_id,
        reference_number=extracted.get("reference_number"),
        status="ready_for_review",
        ai_confidence=confidence,
    )
    session.add(draft)
    await session.flush()
    return draft


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_ai_extraction(self, inbox_item_id: str):
    try:
        return _run_async(_process_extraction(inbox_item_id))
    except Exception as exc:
        logger.exception("AI extraction failed for inbox_item %s", inbox_item_id)
        self.retry(exc=exc)


async def _get_telegram_chat_id(session, company_id) -> int | None:
    result = await session.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status == "active",
        )
    )
    conn = result.scalar_one_or_none()
    return conn.telegram_chat_id if conn else None


def _send_result_to_telegram(
    chat_id: int, item, extracted_data: dict, draft_id: str | None
):

    if draft_id and extracted_data.get("amount"):
        amount = extracted_data.get("amount", "?")
        currency = extracted_data.get("currency", "?")
        vendor = extracted_data.get("vendor", {}).get("name", "")
        date_str = extracted_data.get("transaction_date", "?")
        txn_type = extracted_data.get("transaction_type", "?")
        desc = extracted_data.get("description", "")

        text = (
            f"AI Extraction Complete\n\n"
            f"Type: {txn_type}\n"
            f"Amount: {currency} {amount}\n"
            f"Date: {date_str}\n"
            f"Vendor: {vendor or 'Unknown'}\n"
            f"Description: {desc}\n\n"
            f"Review this draft transaction:"
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "Approve", "callback_data": f"approve:{draft_id}"},
                    {"text": "Edit", "callback_data": f"edit:{draft_id}"},
                    {"text": "Reject", "callback_data": f"reject:{draft_id}"},
                ]
            ]
        }

        send_telegram_response.delay(chat_id, text, reply_markup)
    else:
        send_telegram_response.delay(
            chat_id,
            "AI extraction completed but no draft was created. The extracted data may be insufficient.",
        )
