from sqlalchemy import Column, String, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class AIExtraction(BaseModel, TimestampMixin):
    __tablename__ = "ai_extractions"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    inbox_item_id = Column(
        UUID(as_uuid=True), ForeignKey("inbox_items.id"), nullable=False
    )
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    request_payload = Column(JSONB, nullable=False)
    raw_response = Column(JSONB, nullable=False)
    validated_result = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Numeric(10, 6), nullable=True)
    processing_ms = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)

    inbox_item = relationship("InboxItem", back_populates="ai_extractions")
