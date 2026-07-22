from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class Notification(BaseModel, TimestampMixin):
    __tablename__ = "notifications"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    channel = Column(String(20), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(String, nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="notifications")
    user = relationship("User", foreign_keys=[user_id], lazy="noload")
