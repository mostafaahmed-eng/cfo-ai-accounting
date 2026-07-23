from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.enums import UserRole, MemberStatus


class CompanyCreate(BaseModel):
    name: str
    legal_name: str | None = None
    country_code: str
    base_currency: str
    fiscal_year_start: int = 1
    timezone: str = "UTC"
    tax_number: str | None = None


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    legal_name: str | None
    country_code: str
    base_currency: str
    fiscal_year_start: int
    timezone: str
    tax_number: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitationCreate(BaseModel):
    email: str
    role: UserRole


class InvitationResponse(BaseModel):
    id: UUID
    company_id: UUID
    email: str
    role: UserRole
    status: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class MemberUpdate(BaseModel):
    role: UserRole | None = None
    status: MemberStatus | None = None


class MemberResponse(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID
    role: UserRole
    status: MemberStatus
    joined_at: datetime

    model_config = {"from_attributes": True}
