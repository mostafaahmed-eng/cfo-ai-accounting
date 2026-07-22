from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date


class JournalLineInput(BaseModel):
    account_id: UUID
    description: str | None = None
    debit: float = 0
    credit: float = 0


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str
    source_type: str
    source_id: str | None = None
    currency: str
    lines: list[JournalLineInput]


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
