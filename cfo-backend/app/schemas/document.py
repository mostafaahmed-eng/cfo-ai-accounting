from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class DocumentResponse(BaseModel):
    id: UUID
    company_id: UUID
    inbox_item_id: UUID | None
    original_name: str
    mime_type: str
    size_bytes: int
    document_type: str
    upload_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DownloadURLResponse(BaseModel):
    download_url: str
    expires_at: datetime
