from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class JournalLineResponse(BaseModel):
    id: UUID
    account_id: UUID
    description: str | None
    debit: float
    credit: float
    currency: str
    base_debit: float
    base_credit: float

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: UUID
    company_id: UUID
    entry_number: str
    entry_date: date
    description: str
    source_type: str
    source_id: str | None
    status: str
    currency: str
    exchange_rate: float
    posted_by: UUID | None
    posted_at: datetime | None
    reversed_entry_id: UUID | None
    created_at: datetime
    lines: list[JournalLineResponse] = []

    model_config = {"from_attributes": True}
