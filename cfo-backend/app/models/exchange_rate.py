from sqlalchemy import Column, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class ExchangeRate(BaseModel, TimestampMixin):
    __tablename__ = "exchange_rates"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    base_currency = Column(String(3), nullable=False)
    quote_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    rate_date = Column(Date, nullable=False)
    source = Column(String(50), nullable=False)

    company = relationship("Company", back_populates="exchange_rates")

    __table_args__ = (
        UniqueConstraint("company_id", "base_currency", "quote_currency", "rate_date"),
    )
