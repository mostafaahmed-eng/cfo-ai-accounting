from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.enums import AccountType


class AccountCreate(BaseModel):
    code: str
    name_en: str
    name_ar: str | None = None
    type: AccountType
    subtype: str
    currency: str | None = None
    parent_account_id: UUID | None = None
    is_payment_account: bool = False


class AccountUpdate(BaseModel):
    name_en: str | None = None
    name_ar: str | None = None
    subtype: str | None = None
    currency: str | None = None
    parent_account_id: UUID | None = None
    is_payment_account: bool | None = None
    is_active: bool | None = None


class AccountResponse(BaseModel):
    id: UUID
    company_id: UUID
    code: str
    name_en: str
    name_ar: str | None
    type: AccountType
    subtype: str
    currency: str | None
    parent_account_id: UUID | None
    is_payment_account: bool
    is_system: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportTemplateRequest(BaseModel):
    format: str = "csv"
