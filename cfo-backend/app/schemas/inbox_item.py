from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class TextInput(BaseModel):
    text: str
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

    model_config = {"from_attributes": True}
