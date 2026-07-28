from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

TransactionTypeValue = Literal["expense", "income", "transfer"]


def _normalize_currency(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("Currency must be a three-letter ISO code")
    return normalized


def _normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("Description is required")
    return normalized


def _normalize_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class DraftTransactionUpdate(BaseModel):
    type: TransactionTypeValue | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=4)
    tax_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=4
    )
    currency: str | None = None
    transaction_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    vendor_id: UUID | None = None
    category_account_id: UUID | None = None
    payment_account_id: UUID | None = None
    reference_number: str | None = Field(default=None, max_length=100)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return _normalize_currency(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _normalize_description(value)

    @field_validator("reference_number")
    @classmethod
    def normalize_reference(cls, value: str | None) -> str | None:
        return _normalize_reference(value)


class DraftEditableState(BaseModel):
    type: TransactionTypeValue
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    tax_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    currency: str
    transaction_date: date
    description: str = Field(min_length=1, max_length=5000)
    vendor_id: UUID | None
    category_account_id: UUID | None
    payment_account_id: UUID | None
    reference_number: str | None = Field(default=None, max_length=100)

    _normalize_currency = field_validator("currency")(_normalize_currency)
    _normalize_description = field_validator("description")(_normalize_description)
    _normalize_reference = field_validator("reference_number")(_normalize_reference)


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
