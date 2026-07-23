from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime, timezone
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

router = APIRouter()
settings = get_settings()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if settings.TELEGRAM_WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret token")

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
        connect_result = await db.execute(
            select(TelegramConnection).where(
                TelegramConnection.telegram_chat_id == 0,
                TelegramConnection.status == "pending_chat_id",
            )
        )
        pending = connect_result.scalars().all()
        if pending:
            connection = pending[0]
            connection.telegram_chat_id = chat_id
            connection.status = "active"
            await db.flush()
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
                payload=body,
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
            payload=body,
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
        item = InboxItem(
            id=uuid4(),
            company_id=connection.company_id,
            source="telegram",
            content_type="text",
            original_text=text,
            status="received",
        )
        db.add(item)
        await db.flush()

        send_telegram_response.delay(
            chat_id, "Processing your message... I'll extract financial data shortly."
        )
        run_ai_extraction.delay(str(item.id))
        update.inbox_item_id = str(item.id)
        update.processing_status = "dispatched"
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
            except JournalError as e:
                draft.status = "approved"
                await db.flush()
                send_telegram_response.delay(chat_id, f"Approval failed: {e.detail}")
        else:
            send_telegram_response.delay(
                chat_id, "Draft not found or already processed."
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
        else:
            send_telegram_response.delay(chat_id, "Draft not found.")

    elif data.startswith("edit:"):
        draft_id = data.split(":", 1)[1]
        send_telegram_response.delay(
            chat_id,
            f"To edit draft {draft_id[:8]}..., please use the web dashboard.\n"
            f"Or send a correction message describing what should change.",
        )

    elif data.startswith("extract:"):
        inbox_item_id = data.split(":", 1)[1]
        run_ai_extraction.delay(inbox_item_id)
        send_telegram_response.delay(chat_id, "Re-running extraction...")

    return {"status": "ok"}


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
