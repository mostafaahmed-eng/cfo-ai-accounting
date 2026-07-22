from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from typing import Any


class VendorInfo(BaseModel):
    name: str | None = None
    tax_number: str | None = None


class ConfidenceScores(BaseModel):
    overall: float
    amount: float
    currency: float
    date: float
    category: float


class ExtractionResult(BaseModel):
    document_type: str
    transaction_type: str
    amount: float
    tax_amount: float | None = 0
    currency: str
    transaction_date: date
    vendor: VendorInfo
    description: str
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
