from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class Account(BaseModel, TimestampMixin):
    __tablename__ = "accounts"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    code = Column(String(20), nullable=False)
    name_en = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)
    type = Column(String(20), nullable=False)
    subtype = Column(String(50), nullable=False)
    currency = Column(String(3), nullable=True)
    parent_account_id = Column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    is_payment_account = Column(Boolean, default=False, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company", back_populates="accounts")
    parent_account = relationship("Account", remote_side="Account.id")
    journal_lines = relationship("JournalLine", back_populates="account")

    __table_args__ = (UniqueConstraint("company_id", "code"),)
