from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class BudgetLineInput(BaseModel):
    account_id: UUID
    planned_amount: float
    alert_percentage: float = 80


class BudgetCreate(BaseModel):
    name: str
    period_type: str
    start_date: str
    end_date: str
    currency: str
    lines: list[BudgetLineInput] = []


class BudgetUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    lines: list[BudgetLineInput] | None = None


class BudgetLineResponse(BaseModel):
    id: UUID
    account_id: UUID
    planned_amount: float
    alert_percentage: float

    model_config = {"from_attributes": True}


class BudgetResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    period_type: str
    start_date: str
    end_date: str
    currency: str
    status: str
    created_by: UUID
    created_at: datetime
    lines: list[BudgetLineResponse] = []

    model_config = {"from_attributes": True}
