from sqlalchemy import Column, String, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class Document(BaseModel, TimestampMixin):
    __tablename__ = "documents"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    inbox_item_id = Column(UUID(as_uuid=True), ForeignKey("inbox_items.id"), nullable=True)
    storage_key = Column(String(500), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    document_type = Column(String(20), nullable=False, default="other")
    upload_status = Column(String(20), nullable=False, default="pending")
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    company = relationship("Company", back_populates="documents")
    inbox_item = relationship("InboxItem", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="noload")
