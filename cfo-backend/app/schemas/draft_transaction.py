from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date


class DraftTransactionUpdate(BaseModel):
    type: str | None = None
    amount: float | None = None
    tax_amount: float | None = None
    currency: str | None = None
    transaction_date: date | None = None
    description: str | None = None
    vendor_id: UUID | None = None
    category_account_id: UUID | None = None
    payment_account_id: UUID | None = None
    reference_number: str | None = None


class DraftTransactionResponse(BaseModel):
    id: UUID
    company_id: UUID
    inbox_item_id: UUID | None
    document_id: UUID | None
    type: str
    amount: float
    tax_amount: float
    currency: str
    transaction_date: date
    description: str
    vendor_id: UUID | None
    category_account_id: UUID | None
    payment_account_id: UUID | None
    reference_number: str | None
    status: str
    ai_confidence: float | None
    created_by: UUID | None
    approved_by: UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClarificationRequest(BaseModel):
    question: str
    answer: str
