from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from app.database import get_db
from app.config import get_settings
from app.models.telegram import TelegramConnection
from app.models.user import User
from app.schemas.telegram import TelegramStatusResponse
from app.dependencies import get_current_user, get_current_company_id
from app.services.audit import create_audit_log

router = APIRouter()
settings = get_settings()


@router.post("/telegram/connect", response_model=TelegramStatusResponse)
async def connect_telegram(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status.in_(["active", "pending_chat_id"]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.status == "active":
            return TelegramStatusResponse(
                connected=True,
                bot_username=existing.bot_username,
                chat_id=existing.telegram_chat_id,
                status="active",
            )
        return TelegramStatusResponse(
            connected=False,
            bot_username=existing.bot_username,
            chat_id=0,
            status="pending",
        )

    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username=settings.TELEGRAM_BOT_USERNAME or "bot",
        telegram_chat_id=0,
        connected_by=str(user.id),
        status="pending_chat_id",
    )
    db.add(connection)
    await db.flush()

    await create_audit_log(
        db=db,
        company_id=str(company_id),
        user_id=str(user.id),
        actor_type="user",
        action="telegram.connect_requested",
        entity_type="telegram_connection",
        entity_id=str(connection.id),
    )

    return TelegramStatusResponse(
        connected=False,
        bot_username=connection.bot_username,
        chat_id=0,
        status="pending",
    )


@router.delete("/telegram/disconnect")
async def disconnect_telegram(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status.in_(["active", "pending_chat_id"]),
        )
    )
    connection = result.scalar_one_or_none()
    if connection:
        old_status = connection.status
        connection.status = "disabled"
        await db.flush()
        await create_audit_log(
            db=db,
            company_id=str(company_id),
            user_id=str(user.id),
            actor_type="user",
            action="telegram.disconnected",
            entity_type="telegram_connection",
            entity_id=str(connection.id),
            before_data={"status": old_status},
            after_data={"status": "disabled"},
        )
    return {"message": "Disconnected"}


@router.get("/telegram/status", response_model=TelegramStatusResponse)
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
