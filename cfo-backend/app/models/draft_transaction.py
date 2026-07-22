from sqlalchemy import Column, String, ForeignKey, Numeric, Text, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class DraftTransaction(BaseModel, TimestampMixin):
    __tablename__ = "draft_transactions"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    inbox_item_id = Column(UUID(as_uuid=True), ForeignKey("inbox_items.id"), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    type = Column(String(20), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    tax_amount = Column(Numeric(18, 4), nullable=False, default=0)
    currency = Column(String(3), nullable=False)
    transaction_date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True)
    category_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    payment_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    reference_number = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    ai_confidence = Column(Numeric(5, 4), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="draft_transactions")
    inbox_item = relationship("InboxItem", back_populates="draft_transactions")
    document = relationship("Document", foreign_keys=[document_id], lazy="noload")
    vendor = relationship("Vendor", foreign_keys=[vendor_id], lazy="noload")
    category_account = relationship("Account", foreign_keys=[category_account_id], lazy="noload")
    payment_account = relationship("Account", foreign_keys=[payment_account_id], lazy="noload")
    creator = relationship("User", foreign_keys=[created_by], lazy="noload")
    approver = relationship("User", foreign_keys=[approved_by], lazy="noload")
