from pydantic import BaseModel


class DashboardResponse(BaseModel):
    base_currency: str
    monthly_income: float
    monthly_expenses: float
    net_cash_flow: float
    pending_approvals: int
    recent_transactions: list[dict] = []
    budget_warnings: list[dict] = []


class PnLResponse(BaseModel):
    base_currency: str
    period: str
    revenue: list[dict] = []
    expenses: list[dict] = []
    net_income: float


class CashFlowResponse(BaseModel):
    base_currency: str
    period: str
    operating: float
    investing: float
    financing: float
    net: float
    monthly_data: list[dict] = []


class BalanceSheetResponse(BaseModel):
    base_currency: str
    as_of: str
    assets: list[dict] = []
    liabilities: list[dict] = []
    equity: list[dict] = []
    total_assets: float
    total_liabilities: float
    total_equity: float


class ExpenseByCategoryResponse(BaseModel):
    base_currency: str
    period: str
    categories: list[dict] = []
    total: float


class VendorReportResponse(BaseModel):
    period: str
    vendors: list[dict] = []
    total: float


class BudgetVsActualResponse(BaseModel):
    period: str
    items: list[dict] = []
