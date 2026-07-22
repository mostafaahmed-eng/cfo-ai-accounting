from sqlalchemy import Column, String, SmallInteger, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class Company(BaseModel, TimestampMixin):
    __tablename__ = "companies"

    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    country_code = Column(String(2), nullable=False)
    base_currency = Column(String(3), nullable=False)
    fiscal_year_start = Column(SmallInteger, nullable=False, default=1)
    timezone = Column(String(50), nullable=False, default="UTC")
    tax_number = Column(String(100), nullable=True)

    members = relationship("CompanyMember", back_populates="company", lazy="selectin")
    accounts = relationship("Account", back_populates="company", lazy="selectin")
    inbox_items = relationship("InboxItem", back_populates="company", lazy="noload")
    documents = relationship("Document", back_populates="company", lazy="noload")
    vendors = relationship("Vendor", back_populates="company", lazy="noload")
    draft_transactions = relationship("DraftTransaction", back_populates="company", lazy="noload")
    journal_entries = relationship("JournalEntry", back_populates="company", lazy="noload")
    budgets = relationship("Budget", back_populates="company", lazy="noload")
    notifications = relationship("Notification", back_populates="company", lazy="noload")
    audit_logs = relationship("AuditLog", back_populates="company", lazy="noload")
    telegram_connections = relationship("TelegramConnection", back_populates="company", lazy="noload")
    exchange_rates = relationship("ExchangeRate", back_populates="company", lazy="noload")


class CompanyMember(BaseModel, TimestampMixin):
    __tablename__ = "company_members"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    joined_at = Column(String(30), nullable=False)

    company = relationship("Company", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (UniqueConstraint("company_id", "user_id"),)
