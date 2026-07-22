from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class VendorCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    tax_number: str | None = None
    country_code: str | None = None
    default_expense_account: UUID | None = None
    default_currency: str | None = None


class VendorUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_number: str | None = None
    country_code: str | None = None
    default_expense_account: UUID | None = None
    default_currency: str | None = None
    is_active: bool | None = None


class VendorResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    normalized_name: str
    email: str | None
    phone: str | None
    tax_number: str | None
    country_code: str | None
    default_expense_account: UUID | None
    default_currency: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AliasCreate(BaseModel):
    alias: str


class AliasResponse(BaseModel):
    id: UUID
    vendor_id: UUID
    alias: str
    normalized_alias: str

    model_config = {"from_attributes": True}
