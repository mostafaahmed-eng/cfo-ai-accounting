import secrets
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import (
    get_current_company_id,
    get_current_user,
    get_platform_admin_user,
)
from app.models.telegram import TelegramConnection, TelegramPairing
from app.models.user import User
from app.schemas.telegram import (
    TelegramBotConfigResponse,
    TelegramBotConfigUpdate,
    TelegramStatusResponse,
)
from app.services.audit import create_audit_log
from app.services.telegram_bot_config import (
    get_telegram_config,
    resolve_bot_username,
    save_telegram_config,
)
from app.services.telegram_pairing import create_pairing

router = APIRouter()
settings = get_settings()

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


async def _telegram_get_me(token: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{TELEGRAM_API_BASE}{token}/getMe")
        try:
            return response.json()
        except ValueError:
            return {"ok": False, "description": f"HTTP {response.status_code}"}


@router.post("/telegram/connect", response_model=TelegramStatusResponse)
async def connect_telegram(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    bot_username = (await resolve_bot_username(db)).strip()
    if not bot_username:
        raise HTTPException(
            status_code=503,
            detail=(
                "Telegram is not configured: TELEGRAM_BOT_USERNAME is not set. "
                "Set it to the bot username (without @) before connecting."
            ),
        )

    stale_disabled_result = await db.execute(
        select(TelegramConnection)
        .where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status == "disabled",
            TelegramConnection.telegram_chat_id.is_not(None),
        )
        .with_for_update()
    )
    for stale_connection in stale_disabled_result.scalars().all():
        stale_connection.telegram_chat_id = None

    result = await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == company_id,
            TelegramConnection.status.in_(["active", "pending_chat_id"]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing and existing.status == "active":
        existing.bot_username = bot_username
        return TelegramStatusResponse(
            connected=True,
            bot_username=bot_username,
            chat_id=existing.telegram_chat_id,
            status="active",
        )

    if existing:
        connection = existing
    else:
        disabled_result = await db.execute(
            select(TelegramConnection)
            .where(
                TelegramConnection.company_id == company_id,
                TelegramConnection.status == "disabled",
            )
            .order_by(TelegramConnection.updated_at.desc())
            .limit(1)
            .with_for_update()
        )
        connection = disabled_result.scalar_one_or_none()
        if connection is None:
            connection = TelegramConnection(
                id=uuid4(),
                company_id=company_id,
                bot_username=bot_username,
                telegram_chat_id=None,
                connected_by=str(user.id),
                status="pending_chat_id",
            )
            db.add(connection)

    connection.bot_username = bot_username
    connection.telegram_chat_id = None
    connection.connected_by = str(user.id)
    connection.status = "pending_chat_id"
    await db.flush()

    pairing_creation = await create_pairing(
        db,
        connection=connection,
        company_id=company_id,
        user_id=user.id,
    )
    pairing_link = f"https://t.me/{bot_username}?start={pairing_creation.code}"

    return TelegramStatusResponse(
        connected=False,
        bot_username=bot_username,
        chat_id=None,
        status="pending",
        pairing_code=pairing_creation.code,
        pairing_link=pairing_link,
        pairing_expires_at=pairing_creation.pairing.expires_at,
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
        connection.telegram_chat_id = None
        connection.status = "disabled"
        pending_pairings = await db.execute(
            select(TelegramPairing)
            .where(
                TelegramPairing.connection_id == connection.id,
                TelegramPairing.status == "pending",
            )
            .with_for_update()
        )
        for pairing in pending_pairings.scalars().all():
            pairing.status = "revoked"
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
            after_data={"status": "disabled", "chat_binding_cleared": True},
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
    bot_username = (await resolve_bot_username(db)).strip() or connection.bot_username
    return TelegramStatusResponse(
        connected=True,
        bot_username=bot_username,
        chat_id=connection.telegram_chat_id,
        status="active",
    )


@router.get("/telegram/bot-config", response_model=TelegramBotConfigResponse)
async def get_telegram_bot_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    config = await get_telegram_config(db)
    username = ""
    if config is not None and config.bot_username:
        username = config.bot_username
    if not username:
        username = settings.TELEGRAM_BOT_USERNAME.strip()
    has_token = bool(config is not None and config.bot_token_encrypted) or bool(
        settings.TELEGRAM_BOT_TOKEN
    )
    return TelegramBotConfigResponse(
        configured=bool(username),
        bot_username=username or None,
        has_token=has_token,
    )


@router.put("/telegram/bot-config", response_model=TelegramBotConfigResponse)
async def update_telegram_bot_config(
    data: TelegramBotConfigUpdate,
    user: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
):
    token = data.bot_token.strip()
    if not token:
        raise HTTPException(status_code=422, detail="Bot token is required")

    get_me = await _telegram_get_me(token)
    if not get_me.get("ok"):
        detail = get_me.get("description", "Telegram rejected the bot token")
        raise HTTPException(status_code=422, detail=f"Invalid bot token: {detail}")

    bot_info = get_me.get("result", {})
    verified_username = bot_info.get("username", "") or ""
    username = data.bot_username.strip() or verified_username
    if not username:
        raise HTTPException(
            status_code=422,
            detail="Could not determine the bot username. Enter it manually.",
        )

    config = await get_telegram_config(db)
    existing_secret = config.webhook_secret if config is not None else None
    webhook_secret = existing_secret or secrets.token_urlsafe(32)

    await save_telegram_config(
        db,
        bot_token=token,
        bot_username=username,
        webhook_secret=webhook_secret,
        updated_by=user.id,
    )
    await create_audit_log(
        db=db,
        company_id=None,
        user_id=str(user.id),
        actor_type="user",
        action="telegram.bot_config_updated",
        entity_type="telegram_bot_config",
        entity_id="singleton",
        after_data={"bot_username": username},
    )
    return TelegramBotConfigResponse(
        configured=True,
        bot_username=username,
        has_token=True,
        verified_username=verified_username,
    )
