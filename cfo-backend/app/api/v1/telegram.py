from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID, uuid4
from datetime import datetime, timezone
import copy
import secrets
from app.database import get_db
from app.config import get_settings
from app.models.telegram import TelegramConnection, TelegramUpdate
from app.models.inbox_item import InboxItem
from app.models.user import User
from app.models.draft_transaction import DraftTransaction
from app.schemas.telegram import TelegramStatusResponse
from app.dependencies import get_current_user, get_current_company_id
from app.tasks.ai_extraction import run_ai_extraction
from app.tasks.telegram_responses import (
    send_telegram_response,
    send_telegram_edit,
    answer_telegram_callback,
)
from app.services.audit import create_audit_log
from app.services.telegram_pairing import consume_pairing
from app.services.intake import create_text_inbox
from app.core.text_processing import detect_language

router = APIRouter()
settings = get_settings()


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

    existing = await db.execute(
        select(TelegramUpdate).where(TelegramUpdate.telegram_update_id == update_id)
    )
    if existing.scalar_one_or_none():
        return {"status": "duplicate"}

    callback_query = body.get("callback_query")
    if callback_query:
        return await _handle_callback_query(callback_query, db)

    message = body.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return {"status": "no_chat_id"}

    result = await db.execute(
        select(TelegramConnection).where(TelegramConnection.telegram_chat_id == chat_id)
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
        content_types = ["photo", "document", "voice"]
        for ct in content_types:
            if message.get(ct):
                send_telegram_response.delay(
                    chat_id,
                    f"Received a {ct}. Currently I only support text-based extraction. "
                    "Please type the expense details (e.g., 'Paid $50 for office supplies to Acme Corp on 2025-01-15').",
                )
                update.processing_status = "unsupported_content"
                break

    await db.flush()
    return {"status": "ok"}


async def _handle_callback_query(callback_query: dict, db: AsyncSession):
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

    if data.startswith("approve:"):
        draft_id = data.split(":", 1)[1]
        result = await db.execute(
            select(DraftTransaction).where(
                DraftTransaction.id == draft_id,
                DraftTransaction.company_id == company_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft and draft.status == "ready_for_review":
            from app.services.journal import (
                create_journal_entry_from_draft,
                JournalError,
            )

            draft.status = "approved"
            draft.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()
            try:
                await create_journal_entry_from_draft(db, draft)
                draft.status = "posted"
                await db.flush()
                send_telegram_edit.delay(
                    chat_id,
                    message_id,
                    f"Approved and posted!\nAmount: {draft.currency} {draft.amount}\n{draft.description}",
                )
                await create_audit_log(
                    db=db,
                    company_id=str(company_id),
                    user_id=None,
                    actor_type="telegram",
                    action="draft.approved",
                    entity_type="draft_transaction",
                    entity_id=str(draft.id),
                    before_data={"status": "ready_for_review"},
                    after_data={
                        "status": "posted",
                        "currency": draft.currency,
                        "amount": float(draft.amount),
                    },
                )
                await _audit_callback(
                    db,
                    connection=connection,
                    action="approve",
                    target_type="draft_transaction",
                    target_id=str(draft.id),
                    status="succeeded",
                )
            except JournalError as e:
                draft.status = "approved"
                await db.flush()
                send_telegram_response.delay(chat_id, f"Approval failed: {e.detail}")
                await _audit_callback(
                    db,
                    connection=connection,
                    action="approve",
                    target_type="draft_transaction",
                    target_id=str(draft.id),
                    status="failed",
                )
        else:
            send_telegram_response.delay(
                chat_id, "Draft not found or already processed."
            )
            await _audit_callback(
                db,
                connection=connection,
                action="approve",
                target_type="draft_transaction",
                target_id=draft_id,
                status="denied",
            )

    elif data.startswith("reject:"):
        draft_id = data.split(":", 1)[1]
        result = await db.execute(
            select(DraftTransaction).where(
                DraftTransaction.id == draft_id,
                DraftTransaction.company_id == company_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft:
            old_status = draft.status
            draft.status = "rejected"
            await db.flush()
            send_telegram_edit.delay(
                chat_id,
                message_id,
                f"Rejected.\nAmount: {draft.currency} {draft.amount}\n{draft.description}",
            )
            await create_audit_log(
                db=db,
                company_id=str(company_id),
                user_id=None,
                actor_type="telegram",
                action="draft.rejected",
                entity_type="draft_transaction",
                entity_id=str(draft.id),
                before_data={"status": old_status},
                after_data={"status": "rejected"},
            )
            await _audit_callback(
                db,
                connection=connection,
                action="reject",
                target_type="draft_transaction",
                target_id=str(draft.id),
                status="succeeded",
            )
        else:
            send_telegram_response.delay(chat_id, "Draft not found.")
            await _audit_callback(
                db,
                connection=connection,
                action="reject",
                target_type="draft_transaction",
                target_id=draft_id,
                status="denied",
            )

    elif data.startswith("edit:"):
        draft_id = data.split(":", 1)[1]
        result = await db.execute(
            select(DraftTransaction).where(
                DraftTransaction.id == draft_id,
                DraftTransaction.company_id == company_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft:
            send_telegram_response.delay(
                chat_id,
                f"To edit draft {draft_id[:8]}..., please use the web dashboard.\n"
                f"Or send a correction message describing what should change.",
            )
            callback_status = "succeeded"
        else:
            send_telegram_response.delay(chat_id, "Draft not found.")
            callback_status = "denied"
        await _audit_callback(
            db,
            connection=connection,
            action="edit",
            target_type="draft_transaction",
            target_id=draft_id,
            status=callback_status,
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
