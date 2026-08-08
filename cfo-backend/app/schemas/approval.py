from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ApprovalResponse(BaseModel):
    id: UUID
    company_id: UUID
    entity_type: str
    entity_id: str
    requested_by: UUID | None
    assigned_to: UUID | None
    status: str
    comment: str | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
