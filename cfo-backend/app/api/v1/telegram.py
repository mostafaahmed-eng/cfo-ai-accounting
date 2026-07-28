import copy
import secrets
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.telegram import TelegramFileError, telegram_client
from app.core.text_processing import detect_language
from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.draft_transaction import DraftTransaction
from app.models.inbox_item import InboxItem
from app.models.telegram import TelegramConnection, TelegramUpdate
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.draft_transaction import DraftTransactionUpdate
from app.schemas.telegram import TelegramStatusResponse
from app.services.audit import create_audit_log
from app.services.document_intake import (
    DocumentStorageError,
    store_document_intake,
)
from app.services.document_processing import (
    MIME_EXTENSIONS,
    DocumentValidationError,
    validate_content,
)
from app.services.draft_editing import DraftEditActor, edit_draft
from app.services.intake import create_text_inbox
from app.services.telegram_draft_review import draft_review_message
from app.services.telegram_edit_state import (
    TelegramEditState,
    clear_edit_state,
    get_edit_state,
    set_edit_state,
)
from app.services.telegram_pairing import consume_pairing
from app.tasks.ai_extraction import run_ai_extraction
from app.tasks.receipt_processing import process_receipt
from app.tasks.telegram_responses import (
    answer_telegram_callback,
    send_telegram_edit,
    send_telegram_response,
)

router = APIRouter()
settings = get_settings()
TELEGRAM_EDIT_FIELDS = {
    "vendor",
    "amount",
    "currency",
    "date",
    "description",
    "reference",
    "type",
}
TELEGRAM_EDIT_PROMPTS = {
    "vendor": "Send the exact name of an existing active vendor, or 'none' to clear it.",
    "amount": "Send the corrected positive amount, for example: 125.50",
    "currency": "Send a three-letter currency code, for example: EGP, USD, EUR, or SAR.",
    "date": "Send the corrected date as YYYY-MM-DD.",
    "description": "Send the corrected description.",
    "reference": "Send the corrected invoice/reference number, or 'none' to clear it.",
    "type": "Send one of: expense, income, transfer.",
}


def _verify_webhook_secret(request: Request) -> None:
    insecure_local = (
        settings.ENVIRONMENT == "development"
        and settings.TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK
    )
    if insecure_local:
        return

    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected:
        raise HTTPException(
            status_code=503, detail="Telegram webhook authentication is not configured"
        )

    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Invalid secret token")


def _sanitized_update_payload(body: dict) -> dict:
    sanitized = copy.deepcopy(body)
    message = sanitized.get("message")
    if isinstance(message, dict):
        text = message.get("text")
        if isinstance(text, str) and text.startswith("/start"):
            message["text"] = "/start [REDACTED]"
    return sanitized


async def _vendor_name(db: AsyncSession, draft: DraftTransaction) -> str | None:
    if not draft.vendor_id:
        return None
    result = await db.execute(
        select(Vendor.name).where(
            Vendor.id == draft.vendor_id,
            Vendor.company_id == draft.company_id,
        )
    )
    return result.scalar_one_or_none()


async def _telegram_edit_patch(
    db: AsyncSession,
    *,
    company_id,
    field: str,
    text: str,
) -> DraftTransactionUpdate:
    value = text.strip()
    if field == "vendor":
        if value.casefold() in {"none", "clear", "بدون", "لا يوجد"}:
            return DraftTransactionUpdate(vendor_id=None)
        normalized = " ".join(value.casefold().split())
        result = await db.execute(
            select(Vendor.id).where(
                Vendor.company_id == company_id,
                Vendor.normalized_name == normalized,
                Vendor.is_active,
            )
        )
        vendor_id = result.scalar_one_or_none()
        if vendor_id is None:
            raise HTTPException(
                status_code=422,
                detail="No active vendor with that exact name was found",
            )
        return DraftTransactionUpdate(vendor_id=vendor_id)
    if field == "reference" and value.casefold() in {
        "none",
        "clear",
        "بدون",
        "لا يوجد",
    }:
        return DraftTransactionUpdate(reference_number=None)
    field_map = {
        "amount": "amount",
        "currency": "currency",
        "date": "transaction_date",
        "description": "description",
        "reference": "reference_number",
        "type": "type",
    }
    return DraftTransactionUpdate.model_validate({field_map[field]: value})


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _verify_webhook_secret(request)

    body = await request.json()
    update_id = body.get("update_id")
    if not update_id:
        raise HTTPException(status_code=400, detail="Missing update_id")

    await db.execute(select(func.pg_advisory_xact_lock(update_id)))
    existing = await db.execute(
        select(TelegramUpdate).where(TelegramUpdate.telegram_update_id == update_id)
    )
    if existing.scalar_one_or_none():
        return {"status": "duplicate"}

    callback_query = body.get("callback_query")
    if callback_query:
        return await _handle_callback_query(
            callback_query,
            db,
            update_id=update_id,
            payload=body,
        )

    message = body.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return {"status": "no_chat_id"}

    result = await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.telegram_chat_id == chat_id,
            TelegramConnection.status == "active",
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        text = message.get("text", "")
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            code = parts[1].strip() if len(parts) == 2 else ""
            pairing_result = await consume_pairing(db, code=code, chat_id=chat_id)
            if not pairing_result.succeeded:
                send_telegram_response.delay(
                    chat_id,
                    "Unable to connect. Request a new pairing link from the dashboard.",
                )
                return {"status": "pairing_failed"}

            connection = pairing_result.connection
            assert connection is not None
            send_telegram_response.delay(
                chat_id,
                "Connected! I'm now linked to your company.\n\n"
                "Send me a receipt, invoice, or expense description and I'll extract the financial data.\n\n"
                "Commands:\n"
                "/status — Check connection status\n"
                "/help — Show this message",
            )
            update = TelegramUpdate(
                id=uuid4(),
                connection_id=str(connection.id),
                telegram_update_id=update_id,
                message_id=message.get("message_id"),
                chat_id=chat_id,
                update_type="command",
                payload=_sanitized_update_payload(body),
                processing_status="processed",
            )
            db.add(update)
            await db.flush()
            return {"status": "connected"}

        return {"status": "no_connection"}

    text = message.get("text", "")

    if text and text.startswith("/start"):
        send_telegram_response.delay(
            chat_id,
            "Welcome to AI CFO Bot!\n\n"
            "Send me a receipt, invoice, or expense description and I'll extract the financial data and create a draft transaction.\n\n"
            "Commands:\n"
            "/status — Check connection status\n"
            "/help — Show this message",
        )
        update = TelegramUpdate(
            id=uuid4(),
            connection_id=str(connection.id),
            telegram_update_id=update_id,
            message_id=message.get("message_id"),
            chat_id=chat_id,
            update_type="command",
            payload=_sanitized_update_payload(body),
            processing_status="processed",
        )
        db.add(update)
        await db.flush()
        return {"status": "ok"}

    if text and text.startswith("/status"):
        send_telegram_response.delay(
            chat_id, f"Connected to {connection.bot_username}\nChat ID: {chat_id}"
        )
        update = TelegramUpdate(
            id=uuid4(),
            connection_id=str(connection.id),
            telegram_update_id=update_id,
            message_id=message.get("message_id"),
            chat_id=chat_id,
            update_type="command",
            payload=body,
            processing_status="processed",
        )
        db.add(update)
        await db.flush()
        return {"status": "ok"}

    if text:
        edit_state = await get_edit_state(
            connection_id=str(connection.id),
            company_id=str(connection.company_id),
            chat_id=chat_id,
        )
        if edit_state:
            update = TelegramUpdate(
                id=uuid4(),
                connection_id=str(connection.id),
                telegram_update_id=update_id,
                message_id=message.get("message_id"),
                chat_id=chat_id,
                update_type="draft_edit",
                payload=body,
                processing_status="received",
            )
            db.add(update)
            await db.flush()
            try:
                patch = await _telegram_edit_patch(
                    db,
                    company_id=connection.company_id,
                    field=edit_state.field,
                    text=text,
                )
                draft = await edit_draft(
                    db,
                    company_id=connection.company_id,
                    draft_id=edit_state.draft_id,
                    updates=patch,
                    actor=DraftEditActor(
                        source="telegram",
                        actor_type="telegram",
                        telegram_chat_id=chat_id,
                    ),
                )
            except (HTTPException, ValidationError) as exc:
                detail = (
                    exc.detail
                    if isinstance(exc, HTTPException)
                    else exc.errors()[0]["msg"]
                )
                update.processing_status = "validation_failed"
                await db.flush()
                send_telegram_response.delay(
                    chat_id,
                    f"That value is invalid: {detail}. "
                    f"{TELEGRAM_EDIT_PROMPTS[edit_state.field]}",
                )
                return {"status": "edit_validation_failed"}
            await clear_edit_state(
                connection_id=str(connection.id),
                company_id=str(connection.company_id),
                chat_id=chat_id,
            )
            update.inbox_item_id = draft.inbox_item_id
            update.processing_status = "processed"
            message_text, markup = draft_review_message(
                draft, await _vendor_name(db, draft)
            )
            send_telegram_response.delay(chat_id, message_text, markup)
            return {"status": "draft_updated"}

    update = TelegramUpdate(
        id=uuid4(),
        connection_id=str(connection.id),
        telegram_update_id=update_id,
        message_id=message.get("message_id"),
        chat_id=chat_id,
        update_type="message",
        payload=body,
        processing_status="received",
    )
    db.add(update)

    if text:
        creation = await create_text_inbox(
            db,
            company_id=connection.company_id,
            text=text,
            language=detect_language(text),
            source="telegram",
            source_reference=str(update_id),
        )
        item = creation.item

        send_telegram_response.delay(
            chat_id, "Processing your message... I'll extract financial data shortly."
        )
        update.inbox_item_id = str(item.id)
        update.processing_status = "dispatched"
        await db.flush()
        await db.commit()
        if creation.created:
            run_ai_extraction.delay(str(item.id))
    else:
        photo = message.get("photo")
        telegram_document = message.get("document")
        attachment = None
        if isinstance(photo, list) and photo:
            largest = photo[-1]
            attachment = {
                "file_id": largest.get("file_id"),
                "file_size": largest.get("file_size"),
                "mime_type": "image/jpeg",
                "filename": f"{largest.get('file_unique_id', 'telegram-photo')}.jpg",
            }
        elif isinstance(telegram_document, dict):
            attachment = {
                "file_id": telegram_document.get("file_id"),
                "file_size": telegram_document.get("file_size"),
                "mime_type": (telegram_document.get("mime_type") or "").lower(),
                "filename": telegram_document.get("file_name") or "telegram-document",
            }

        if attachment and attachment["mime_type"] in MIME_EXTENSIONS:
            try:
                if (
                    attachment["file_size"] is not None
                    and int(attachment["file_size"]) > settings.MAX_UPLOAD_SIZE
                ):
                    raise DocumentValidationError(
                        "file_too_large", "File exceeds upload limit"
                    )
                content = await telegram_client.download_file(attachment["file_id"])
                validated = validate_content(content, attachment["mime_type"])
                stored = await store_document_intake(
                    db,
                    company_id=connection.company_id,
                    validated=validated,
                    original_name=attachment["filename"],
                    source="telegram",
                    source_reference=str(update_id),
                    submitted_by=None,
                )
            except DocumentValidationError as exc:
                send_telegram_response.delay(
                    chat_id,
                    f"I couldn't accept that receipt: {exc.detail}. "
                    "Please send a JPG, PNG, or PDF up to 10MB.",
                )
                update.processing_status = "unsupported_content"
            except (TelegramFileError, httpx.HTTPError, DocumentStorageError):
                send_telegram_response.delay(
                    chat_id,
                    "I couldn't download or store that receipt right now. "
                    "Please try again shortly.",
                )
                update.processing_status = "attachment_failed"
            else:
                update.inbox_item_id = str(stored.item.id)
                update.processing_status = "dispatched"
                await db.commit()
                send_telegram_response.delay(
                    chat_id,
                    "Processing your receipt... I'll extract the financial data shortly.",
                )
                if stored.dispatch_processing:
                    process_receipt.delay(str(stored.item.id), str(stored.document.id))
        else:
            unsupported_type = next(
                (
                    content_type
                    for content_type in (
                        "document",
                        "voice",
                        "audio",
                        "video",
                        "video_note",
                        "sticker",
                        "animation",
                    )
                    if message.get(content_type)
                ),
                "content",
            )
            send_telegram_response.delay(
                chat_id,
                f"I can't process that {unsupported_type}. "
                "Please send expense text, a JPG/PNG receipt photo, or a PDF up to 10MB.",
            )
            update.processing_status = "unsupported_content"

    await db.flush()
    return {"status": "ok"}


async def _handle_callback_query(
    callback_query: dict,
    db: AsyncSession,
    *,
    update_id: int | None = None,
    payload: dict | None = None,
):
    cb_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")

    if not chat_id or not message_id:
        return {"status": "invalid_callback"}

    answer_telegram_callback.delay(cb_id)

    conn_result = await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.telegram_chat_id == chat_id,
            TelegramConnection.status == "active",
        )
    )
    connection = conn_result.scalar_one_or_none()
    if not connection:
        send_telegram_response.delay(chat_id, "Connection not found.")
        return {"status": "no_connection"}

    company_id = connection.company_id

    callback_update = None
    if update_id is not None:
        callback_update = TelegramUpdate(
            id=uuid4(),
            connection_id=str(connection.id),
            telegram_update_id=update_id,
            message_id=message_id,
            chat_id=chat_id,
            update_type="callback",
            payload=payload or {"callback_query": callback_query},
            processing_status="processed",
        )
        db.add(callback_update)
        await db.flush()

    if data.startswith("confirm:"):
        draft_id = data.split(":", 1)[1]
        result = await db.execute(
            select(DraftTransaction).where(
                DraftTransaction.id == draft_id,
                DraftTransaction.company_id == company_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft and draft.status == "needs_clarification":
            await clear_edit_state(
                connection_id=str(connection.id),
                company_id=str(company_id),
                chat_id=chat_id,
            )
            if callback_update is not None:
                callback_update.inbox_item_id = draft.inbox_item_id
            draft.status = "ready_for_review"
            await db.flush()
            send_telegram_edit.delay(
                chat_id,
                message_id,
                "Thanks! This has been sent for review. ✅",
            )
            await _audit_callback(
                db,
                connection=connection,
                action="confirm",
                target_type="draft_transaction",
                target_id=str(draft.id),
                status="succeeded",
            )
        else:
            send_telegram_response.delay(
                chat_id, "This confirmation is no longer available."
            )
            await _audit_callback(
                db,
                connection=connection,
                action="confirm",
                target_type="draft_transaction",
                target_id=draft_id,
                status="denied",
            )

    elif data.startswith("edit_cancel:"):
        draft_id = data.split(":", 1)[1]
        await clear_edit_state(
            connection_id=str(connection.id),
            company_id=str(company_id),
            chat_id=chat_id,
        )
        result = await db.execute(
            select(DraftTransaction).where(
                DraftTransaction.id == draft_id,
                DraftTransaction.company_id == company_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft:
            message_text, markup = draft_review_message(
                draft, await _vendor_name(db, draft)
            )
            send_telegram_edit.delay(chat_id, message_id, message_text, markup)
            callback_status = "succeeded"
        else:
            send_telegram_response.delay(chat_id, "Draft not found.")
            callback_status = "denied"
        await _audit_callback(
            db,
            connection=connection,
            action="edit_cancel",
            target_type="draft_transaction",
            target_id=draft_id,
            status=callback_status,
        )

    elif data.startswith("edit:"):
        parts = data.split(":", 2)
        field = parts[1] if len(parts) == 3 else ""
        draft_id = parts[2] if len(parts) == 3 else ""
        result = await db.execute(
            select(DraftTransaction).where(
                DraftTransaction.id == draft_id,
                DraftTransaction.company_id == company_id,
            )
        )
        draft = result.scalar_one_or_none()
        if (
            field in TELEGRAM_EDIT_FIELDS
            and draft
            and draft.status in {"draft", "needs_clarification", "ready_for_review"}
        ):
            await set_edit_state(
                TelegramEditState(
                    connection_id=str(connection.id),
                    company_id=str(company_id),
                    chat_id=chat_id,
                    draft_id=str(draft.id),
                    field=field,
                )
            )
            send_telegram_edit.delay(
                chat_id,
                message_id,
                TELEGRAM_EDIT_PROMPTS[field],
                {
                    "inline_keyboard": [
                        [
                            {
                                "text": "Cancel edit",
                                "callback_data": f"edit_cancel:{draft.id}",
                            }
                        ]
                    ]
                },
            )
            callback_status = "succeeded"
        else:
            send_telegram_response.delay(
                chat_id, "This draft or field is no longer editable."
            )
            callback_status = "denied"
        await _audit_callback(
            db,
            connection=connection,
            action=f"edit_{field or 'invalid'}",
            target_type="draft_transaction",
            target_id=draft_id or "invalid",
            status=callback_status,
        )

    elif data.startswith("correct:"):
        draft_id = data.split(":", 1)[1]
        result = await db.execute(
            select(DraftTransaction).where(
                DraftTransaction.id == draft_id,
                DraftTransaction.company_id == company_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft and draft.status in ("needs_clarification", "ready_for_review"):
            if callback_update is not None:
                callback_update.inbox_item_id = draft.inbox_item_id
            message_text, markup = draft_review_message(
                draft, await _vendor_name(db, draft)
            )
            send_telegram_edit.delay(
                chat_id,
                message_id,
                message_text,
                markup,
            )
            await _audit_callback(
                db,
                connection=connection,
                action="correct",
                target_type="draft_transaction",
                target_id=str(draft.id),
                status="succeeded",
            )
        else:
            send_telegram_response.delay(
                chat_id, "This correction request is no longer available."
            )
            await _audit_callback(
                db,
                connection=connection,
                action="correct",
                target_type="draft_transaction",
                target_id=draft_id,
                status="denied",
            )

    elif data.startswith(("approve:", "reject:")):
        action, draft_id = data.split(":", 1)
        send_telegram_response.delay(
            chat_id,
            "Accounting approval is only available in the dashboard.",
        )
        await _audit_callback(
            db,
            connection=connection,
            action=action,
            target_type="draft_transaction",
            target_id=draft_id,
            status="denied",
        )

    elif data.startswith("extract:"):
        inbox_item_id = data.split(":", 1)[1]
        try:
            inbox_uuid = UUID(inbox_item_id)
        except (TypeError, ValueError):
            inbox_uuid = None
        inbox_item = None
        if inbox_uuid:
            inbox_result = await db.execute(
                select(InboxItem).where(
                    InboxItem.id == inbox_uuid,
                    InboxItem.company_id == company_id,
                )
            )
            inbox_item = inbox_result.scalar_one_or_none()
        if inbox_item:
            run_ai_extraction.delay(str(inbox_item.id))
            send_telegram_response.delay(chat_id, "Re-running extraction...")
            callback_status = "succeeded"
        else:
            send_telegram_response.delay(chat_id, "Inbox item not found.")
            callback_status = "denied"
        await _audit_callback(
            db,
            connection=connection,
            action="extract",
            target_type="inbox_item",
            target_id=inbox_item_id,
            status=callback_status,
        )

    return {"status": "ok"}


async def _audit_callback(
    db: AsyncSession,
    *,
    connection: TelegramConnection,
    action: str,
    target_type: str,
    target_id: str,
    status: str,
) -> None:
    await create_audit_log(
        db=db,
        company_id=str(connection.company_id),
        user_id=None,
        actor_type="telegram",
        action=f"telegram.callback_{action}",
        entity_type=target_type,
        entity_id=target_id,
        after_data={
            "connection_id": str(connection.id),
            "status": status,
        },
    )


@router.get("/status", response_model=TelegramStatusResponse)
async def telegram_status(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status == "active",
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        return TelegramStatusResponse(connected=False)
    return TelegramStatusResponse(
        connected=True,
        bot_username=connection.bot_username,
        chat_id=connection.telegram_chat_id,
        status="active",
    )
