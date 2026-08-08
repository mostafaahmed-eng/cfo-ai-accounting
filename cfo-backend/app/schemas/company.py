from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.enums import MemberStatus, UserRole


class CompanyCreate(BaseModel):
    name: str
    legal_name: str | None = None
    country_code: str
    base_currency: str
    fiscal_year_start: int = 1
    timezone: str = "UTC"
    tax_number: str | None = None


class CompanyUpdate(BaseModel):
    """Editable company fields.

    ``base_currency`` is intentionally NOT editable after creation because
    posted journal entries, exchange rates and reports are all denominated in
    the base currency; changing it mid-life would corrupt accounting history.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    fiscal_year_start: int | None = Field(default=None, ge=1, le=12)
    timezone: str | None = Field(default=None, max_length=50)
    tax_number: str | None = Field(default=None, max_length=100)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("Country code must be a two-letter ISO code")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Company name is required")
        return normalized

    @field_validator("tax_number")
    @classmethod
    def normalize_tax_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


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


class MemberDetailResponse(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID
    email: str
    name: str
    role: UserRole
    status: MemberStatus
    joined_at: datetime

    model_config = {"from_attributes": True}


class InvitationDetailResponse(BaseModel):
    id: UUID
    company_id: UUID
    email: str
    role: UserRole
    status: Literal["pending", "accepted", "expired", "revoked"] | str
    invited_by: UUID
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
