from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class VendorInfo(BaseModel):
    name: str | None = None
    tax_number: str | None = None


class ConfidenceScores(BaseModel):
    overall: float = Field(ge=0, le=1)
    amount: float = Field(ge=0, le=1)
    currency: float = Field(ge=0, le=1)
    date: float = Field(ge=0, le=1)
    category: float = Field(ge=0, le=1)


class ExtractionResult(BaseModel):
    document_type: Literal["receipt", "invoice", "text_transaction", "unknown"]
    transaction_type: Literal["expense", "income", "transfer", "unknown"]
    amount: float = Field(gt=0)
    tax_amount: float | None = Field(default=0, ge=0)
    currency: str = Field(min_length=3, max_length=3)
    transaction_date: date | None = None
    vendor: VendorInfo
    description: str = Field(min_length=1)
    category_hint: str | None = None
    payment_method_hint: str | None = None
    reference_number: str | None = None
    language: str
    confidence: ConfidenceScores
    needs_clarification: bool = False
    questions: list[str] = []


class AIExtractionResponse(BaseModel):
    id: UUID
    status: str
    validated_result: dict[str, Any] | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    processing_ms: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
