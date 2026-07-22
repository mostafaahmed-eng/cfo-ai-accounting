from sqlalchemy import Column, String, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, TimestampMixin


class Budget(BaseModel, TimestampMixin):
    __tablename__ = "budgets"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name = Column(String(255), nullable=False)
    period_type = Column(String(20), nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    company = relationship("Company", back_populates="budgets")
    creator = relationship("User", foreign_keys=[created_by], lazy="noload")
    lines = relationship(
        "BudgetLine",
        back_populates="budget",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BudgetLine(BaseModel, TimestampMixin):
    __tablename__ = "budget_lines"

    budget_id = Column(UUID(as_uuid=True), ForeignKey("budgets.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    planned_amount = Column(Numeric(18, 4), nullable=False)
    alert_percentage = Column(Numeric(5, 2), nullable=False, default=80)

    budget = relationship("Budget", back_populates="lines")
    account = relationship("Account", foreign_keys=[account_id], lazy="noload")

    __table_args__ = (UniqueConstraint("budget_id", "account_id"),)
