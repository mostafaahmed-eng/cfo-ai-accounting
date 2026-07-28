from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.user import User
from app.schemas.report import (
    BalanceSheetResponse,
    BudgetVsActualResponse,
    CashFlowResponse,
    DashboardResponse,
    ExpenseByCategoryResponse,
    PnLResponse,
    VendorReportResponse,
)
from app.services.report import ReportService

router = APIRouter()


def _parse_iso_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be a valid ISO date (YYYY-MM-DD)",
        ) from exc


def _report_range(
    start_date: str | None, end_date: str | None
) -> tuple[date | None, date | None]:
    parsed_start = _parse_iso_date(start_date, "start_date")
    parsed_end = _parse_iso_date(end_date, "end_date")
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise HTTPException(
            status_code=400,
            detail="start_date must not be after end_date",
        )
    return parsed_start, parsed_end


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    start_date: str | None = None,
    end_date: str | None = None,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    parsed_start, parsed_end = _report_range(start_date, end_date)
    return await ReportService.get_dashboard(db, company_id, parsed_start, parsed_end)


@router.get("/profit-and-loss", response_model=PnLResponse)
async def profit_and_loss(
    start_date: str | None = None,
    end_date: str | None = None,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    parsed_start, parsed_end = _report_range(start_date, end_date)
    return await ReportService.get_profit_and_loss(
        db, company_id, parsed_start, parsed_end
    )


@router.get("/cash-flow", response_model=CashFlowResponse)
async def cash_flow(
    start_date: str | None = None,
    end_date: str | None = None,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    parsed_start, parsed_end = _report_range(start_date, end_date)
    return await ReportService.get_cash_flow(db, company_id, parsed_start, parsed_end)


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def balance_sheet(
    as_of: str | None = None,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService.get_balance_sheet(
        db, company_id, _parse_iso_date(as_of, "as_of")
    )


@router.get("/expenses-by-category", response_model=ExpenseByCategoryResponse)
async def expenses_by_category(
    start_date: str | None = None,
    end_date: str | None = None,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    parsed_start, parsed_end = _report_range(start_date, end_date)
    return await ReportService.get_expenses_by_category(
        db, company_id, parsed_start, parsed_end
    )


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
