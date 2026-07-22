from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.report import (
    DashboardResponse,
    PnLResponse,
    CashFlowResponse,
    BalanceSheetResponse,
    ExpenseByCategoryResponse,
    VendorReportResponse,
    BudgetVsActualResponse,
)
from app.dependencies import get_current_user, get_current_company_id
from app.services.report import ReportService

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_dashboard(db, company_id)


@router.get("/profit-and-loss", response_model=PnLResponse)
async def profit_and_loss(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_profit_and_loss(db, company_id)


@router.get("/cash-flow", response_model=CashFlowResponse)
async def cash_flow(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_cash_flow(db, company_id)


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def balance_sheet(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_balance_sheet(db, company_id)


@router.get("/expenses-by-category", response_model=ExpenseByCategoryResponse)
async def expenses_by_category(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_expenses_by_category(db, company_id)


@router.get("/vendors", response_model=VendorReportResponse)
async def vendor_report(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_vendors(db, company_id)


@router.get("/budget-vs-actual", response_model=BudgetVsActualResponse)
async def budget_vs_actual(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_budget_vs_actual(db, company_id)
