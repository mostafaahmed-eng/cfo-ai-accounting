from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from app.database import get_db
from app.config import get_settings
from app.models.telegram import TelegramConnection
from app.models.user import User
from app.schemas.telegram import TelegramConnectRequest, TelegramStatusResponse
from app.dependencies import get_current_user, get_current_company_id

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
            TelegramConnection.status == "active"
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return TelegramStatusResponse(connected=True, bot_username=existing.bot_username, chat_id=existing.telegram_chat_id, status="active")

    connection = TelegramConnection(
        id=uuid4(), company_id=company_id, bot_username=settings.TELEGRAM_BOT_USERNAME,
        telegram_chat_id=0, connected_by=str(user.id), status="active",
    )
    db.add(connection)
    await db.flush()
    return TelegramStatusResponse(connected=True, bot_username=connection.bot_username, chat_id=connection.telegram_chat_id, status="active")


@router.delete("/telegram/disconnect")
async def disconnect_telegram(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status == "active"
        )
    )
    connection = result.scalar_one_or_none()
    if connection:
        connection.status = "disabled"
        await db.flush()
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
            TelegramConnection.status == "active"
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        return TelegramStatusResponse(connected=False)
    return TelegramStatusResponse(connected=True, bot_username=connection.bot_username, chat_id=connection.telegram_chat_id, status="active")
