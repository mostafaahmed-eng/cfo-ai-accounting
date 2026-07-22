from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class ApprovalRequest(BaseModel, TimestampMixin):
    __tablename__ = "approval_requests"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    entity_type = Column(String(20), nullable=False)
    entity_id = Column(String, nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    comment = Column(String, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    company = relationship("Company", lazy="noload")
    requester = relationship("User", foreign_keys=[requested_by], lazy="noload")
    assignee = relationship("User", foreign_keys=[assigned_to], lazy="noload")
    resolver = relationship("User", foreign_keys=[resolved_by], lazy="noload")
