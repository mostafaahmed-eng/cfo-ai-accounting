from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.crypto import decrypt_secret
from app.models.base import BaseModel, TimestampMixin


class TelegramBotConfig(BaseModel, TimestampMixin):
    __tablename__ = "telegram_bot_config"

    bot_username = Column(String(100), nullable=True)
    bot_token_encrypted = Column(Text, nullable=True)
    webhook_secret = Column(Text, nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    updater = relationship("User", foreign_keys=[updated_by], lazy="noload")

    @property
    def bot_token(self) -> str | None:
        if not self.bot_token_encrypted:
            return None
        return decrypt_secret(self.bot_token_encrypted)


class TelegramConnection(BaseModel, TimestampMixin):
    __tablename__ = "telegram_connections"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    bot_username = Column(String(100), nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=True)
    connected_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="active")

    company = relationship("Company", back_populates="telegram_connections")
    connector = relationship("User", foreign_keys=[connected_by], lazy="noload")

    __table_args__ = (UniqueConstraint("telegram_chat_id"),)


class TelegramPairing(BaseModel, TimestampMixin):
    __tablename__ = "telegram_pairings"

    connection_id = Column(
        UUID(as_uuid=True), ForeignKey("telegram_connections.id"), nullable=False
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    secret_hash = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="pending")
    expires_at = Column(DateTime, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    consumed_by_chat_id = Column(BigInteger, nullable=True)
    failed_attempts = Column(BigInteger, nullable=False, default=0)
    last_failed_at = Column(DateTime, nullable=True)

    connection = relationship("TelegramConnection", lazy="noload")
    company = relationship("Company", lazy="noload")
    creator = relationship("User", foreign_keys=[created_by], lazy="noload")

    __table_args__ = (
        Index(
            "ix_telegram_pairings_connection_status",
            "connection_id",
            "status",
        ),
    )


class TelegramUpdate(BaseModel, TimestampMixin):
    __tablename__ = "telegram_updates"

    connection_id = Column(
        UUID(as_uuid=True), ForeignKey("telegram_connections.id"), nullable=False
    )
    telegram_update_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=False)
    update_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    processing_status = Column(String(20), nullable=False, default="received")
    inbox_item_id = Column(
        UUID(as_uuid=True), ForeignKey("inbox_items.id"), nullable=True
    )

    connection = relationship("TelegramConnection", lazy="noload")
    inbox_item = relationship("InboxItem", lazy="noload")

    __table_args__ = (UniqueConstraint("telegram_update_id"),)
