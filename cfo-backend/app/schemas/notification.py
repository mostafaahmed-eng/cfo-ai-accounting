from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class NotificationResponse(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID | None
    channel: str
    type: str
    title: str
    message: str
    entity_type: str | None
    entity_id: str | None
    status: str
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
