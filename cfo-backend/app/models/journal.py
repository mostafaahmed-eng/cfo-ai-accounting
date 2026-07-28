from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class JournalEntry(BaseModel, TimestampMixin):
    __tablename__ = "journal_entries"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    entry_number = Column(String(50), nullable=False)
    entry_date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    source_type = Column(String(20), nullable=False)
    source_id = Column(String, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    currency = Column(String(3), nullable=False)
    exchange_rate = Column(Numeric(18, 8), nullable=False, default=1)
    posted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    reversed_entry_id = Column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )

    company = relationship("Company", back_populates="journal_entries")
    lines = relationship(
        "JournalLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    poster = relationship("User", foreign_keys=[posted_by], lazy="noload")
    reversed_entry = relationship(
        "JournalEntry",
        remote_side="JournalEntry.id",
        foreign_keys=[reversed_entry_id],
        lazy="noload",
    )

    __table_args__ = (UniqueConstraint("company_id", "entry_number"),)


class JournalLine(BaseModel, TimestampMixin):
    __tablename__ = "journal_lines"

    journal_entry_id = Column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=False
    )
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    description = Column(String, nullable=True)
    debit = Column(Numeric(18, 4), nullable=False, default=0)
    credit = Column(Numeric(18, 4), nullable=False, default=0)
    currency = Column(String(3), nullable=False)
    base_debit = Column(Numeric(18, 4), nullable=False, default=0)
    base_credit = Column(Numeric(18, 4), nullable=False, default=0)

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account", back_populates="journal_lines", lazy="noload")

    __table_args__ = (
        CheckConstraint("debit >= 0", name="ck_debit_non_negative"),
        CheckConstraint("credit >= 0", name="ck_credit_non_negative"),
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (debit > 0 AND credit = 0)",
            name="ck_debit_xor_credit",
        ),
    )
