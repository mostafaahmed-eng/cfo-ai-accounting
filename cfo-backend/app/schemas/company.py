from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.enums import MemberStatus, UserRole


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


class CompanyMembershipResponse(BaseModel):
    membership_id: UUID
    company_id: UUID
    company_name: str
    role: UserRole


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
