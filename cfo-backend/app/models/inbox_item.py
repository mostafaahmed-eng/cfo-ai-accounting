from sqlalchemy import Column, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class InboxItem(BaseModel, TimestampMixin):
    __tablename__ = "inbox_items"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    source = Column(String(20), nullable=False)
    source_reference = Column(String(255), nullable=True)
    content_type = Column(String(20), nullable=False)
    original_text = Column(String, nullable=True)
    detected_language = Column(String(10), nullable=False, default="unknown")
    status = Column(String(20), nullable=False, default="received")
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(String, nullable=True)
    idempotency_key = Column(String(255), nullable=True)
    processed_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="inbox_items")
    submitter = relationship("User", foreign_keys=[submitted_by], lazy="noload")
    ai_extractions = relationship(
        "AIExtraction", back_populates="inbox_item", lazy="noload"
    )
    documents = relationship("Document", back_populates="inbox_item", lazy="noload")
    draft_transactions = relationship(
        "DraftTransaction", back_populates="inbox_item", lazy="noload"
    )

    __table_args__ = (UniqueConstraint("company_id", "source", "idempotency_key"),)
