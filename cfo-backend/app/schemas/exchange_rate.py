from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExchangeRateCreate(BaseModel):
    base_currency: str
    quote_currency: str
    rate: float = Field(
        gt=0,
        description="Base-currency units per one unit of the quote currency",
    )
    rate_date: date
    source: str

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a three-letter ISO code")
        return normalized


class ExchangeRateResponse(BaseModel):
    id: UUID
    base_currency: str
    quote_currency: str
    rate: float
    rate_date: date
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
