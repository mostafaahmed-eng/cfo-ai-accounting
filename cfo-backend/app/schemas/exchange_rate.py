from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class ExchangeRateCreate(BaseModel):
    base_currency: str
    quote_currency: str
    rate: float
    rate_date: date
    source: str


class ExchangeRateResponse(BaseModel):
    id: UUID
    base_currency: str
    quote_currency: str
    rate: float
    rate_date: date
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
