"""Telegram bot credentials stored in the database.

Bot credentials can be configured from the dashboard (Settings -> Telegram)
instead of being limited to environment variables. Values are stored in a
singleton row; the bot token is encrypted with the app ENCRYPTION_KEY.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.crypto import encrypt_secret
from app.models.telegram import TelegramBotConfig

logger = logging.getLogger(__name__)


async def get_telegram_config(db: AsyncSession) -> TelegramBotConfig | None:
    result = await db.execute(select(TelegramBotConfig).order_by(TelegramBotConfig.id))
    return result.scalars().first()


async def resolve_bot_token(db: AsyncSession) -> str:
    config = await get_telegram_config(db)
    if config is not None and config.bot_token:
        return config.bot_token
    return get_settings().TELEGRAM_BOT_TOKEN


async def resolve_bot_username(db: AsyncSession) -> str:
    config = await get_telegram_config(db)
    if config is not None and config.bot_username:
        return config.bot_username
    return get_settings().TELEGRAM_BOT_USERNAME


async def resolve_webhook_secret(db: AsyncSession) -> str:
    config = await get_telegram_config(db)
    if config is not None and config.webhook_secret:
        return config.webhook_secret
    return get_settings().TELEGRAM_WEBHOOK_SECRET


async def save_telegram_config(
    db: AsyncSession,
    *,
    bot_token: str,
    bot_username: str,
    webhook_secret: str | None = None,
    updated_by,
) -> TelegramBotConfig:
    config = await get_telegram_config(db)
    if config is None:
        config = TelegramBotConfig()
        db.add(config)
    config.bot_token_encrypted = encrypt_secret(bot_token)
    config.bot_username = bot_username or None
    config.webhook_secret = webhook_secret
    config.updated_by = updated_by
    await db.flush()
    return config


def make_session_factory():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_size=2, max_overflow=2)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def db_bot_token() -> str:
    try:
        factory = make_session_factory()
        async with factory() as session:
            return await resolve_bot_token(session)
    except Exception:
        logger.warning(
            "Could not load telegram bot token from DB; using environment value",
            exc_info=True,
        )
        return get_settings().TELEGRAM_BOT_TOKEN
