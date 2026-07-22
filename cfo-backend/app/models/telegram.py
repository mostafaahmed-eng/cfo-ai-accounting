from sqlalchemy import Column, String, ForeignKey, BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class TelegramConnection(BaseModel, TimestampMixin):
    __tablename__ = "telegram_connections"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    bot_username = Column(String(100), nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=False)
    connected_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="active")

    company = relationship("Company", back_populates="telegram_connections")
    connector = relationship("User", foreign_keys=[connected_by], lazy="noload")

    __table_args__ = (UniqueConstraint("telegram_chat_id"),)


class TelegramUpdate(BaseModel, TimestampMixin):
    __tablename__ = "telegram_updates"

    connection_id = Column(UUID(as_uuid=True), ForeignKey("telegram_connections.id"), nullable=False)
    telegram_update_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=False)
    update_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    processing_status = Column(String(20), nullable=False, default="received")
    inbox_item_id = Column(UUID(as_uuid=True), ForeignKey("inbox_items.id"), nullable=True)

    connection = relationship("TelegramConnection", lazy="noload")
    inbox_item = relationship("InboxItem", lazy="noload")

    __table_args__ = (UniqueConstraint("telegram_update_id"),)
