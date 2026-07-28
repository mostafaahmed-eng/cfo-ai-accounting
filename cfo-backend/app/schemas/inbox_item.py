from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    language: str | None = None
    idempotency_key: str | None = None


class InboxItemResponse(BaseModel):
    id: UUID
    company_id: UUID
    source: str
    content_type: str
    original_text: str | None
    detected_language: str
    status: str
    error_code: str | None
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None
    duplicate_status: str
    duplicate_reason: str | None

    model_config = {"from_attributes": True}
