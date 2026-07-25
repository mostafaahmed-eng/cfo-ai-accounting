from calendar import monthrange
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.approval import ApprovalRequest
from app.models.budget import Budget, BudgetLine
from app.models.company import Company
from app.models.draft_transaction import DraftTransaction
from app.models.journal import JournalEntry, JournalLine
from app.models.vendor import Vendor
from app.schemas.report import (
    BalanceSheetResponse,
    BudgetVsActualResponse,
    CashFlowResponse,
    DashboardResponse,
    ExpenseByCategoryResponse,
    PnLResponse,
    VendorReportResponse,
)


class ReportService:
    @staticmethod
    def _net_income(total_revenue: float, total_expenses: float) -> float:
        return total_revenue - total_expenses

    @staticmethod
    async def _base_currency(db: AsyncSession, company_id: str) -> str:
        result = await db.execute(
            select(Company.base_currency).where(Company.id == company_id)
        )
        return result.scalar_one()

    @staticmethod
    def _period(
        start_date: date | None, end_date: date | None
    ) -> tuple[date, date, bool]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        default_start = now.date().replace(day=1)
        default_end = now.date().replace(
            day=monthrange(now.year, now.month)[1]
        )
        is_default = start_date is None and end_date is None
        return start_date or default_start, end_date or default_end, is_default

    @staticmethod
    def _period_label(start_date: date, end_date: date, is_default: bool) -> str:
        return (
            start_date.strftime("%Y-%m")
            if is_default
            else f"{start_date.isoformat()} to {end_date.isoformat()}"
        )

    @staticmethod
    async def get_dashboard(
        db: AsyncSession,
        company_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> DashboardResponse:
        period_start, period_end, _ = ReportService._period(start_date, end_date)

        # Income: sum of credit on revenue accounts in the selected period
        income_result = await db.execute(
            select(func.coalesce(func.sum(JournalLine.base_credit), 0))
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
                Account.type == "revenue",
            )
        )
        monthly_income = float(income_result.scalar() or 0)

        # Expenses: sum of debit on expense accounts in the selected period
        expense_result = await db.execute(
            select(func.coalesce(func.sum(JournalLine.base_debit), 0))
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
                Account.type == "expense",
            )
        )
        monthly_expenses = float(expense_result.scalar() or 0)

        # Pending approvals
        pending_result = await db.execute(
            select(func.count())
            .select_from(ApprovalRequest)
            .where(
                ApprovalRequest.company_id == company_id,
                ApprovalRequest.status == "pending",
            )
        )
        pending_approvals = int(pending_result.scalar() or 0)

        # Recent transactions from draft_transactions
        recent_result = await db.execute(
            select(DraftTransaction)
            .where(DraftTransaction.company_id == company_id)
            .order_by(DraftTransaction.created_at.desc())
            .limit(5)
        )
        recent_txns = []
        for tx in recent_result.scalars().all():
            recent_txns.append(
                {
                    "description": tx.description,
                    "date": str(tx.transaction_date),
                    "amount": float(tx.amount) * (-1 if tx.type == "expense" else 1),
                    "currency": tx.currency,
                    "status": tx.status,
                }
            )

        return DashboardResponse(
            base_currency=await ReportService._base_currency(db, company_id),
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            net_cash_flow=monthly_income - monthly_expenses,
            pending_approvals=pending_approvals,
            recent_transactions=recent_txns,
            budget_warnings=[],
        )

    @staticmethod
    async def get_profit_and_loss(
        db: AsyncSession,
        company_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> PnLResponse:
        period_start, period_end, is_default = ReportService._period(
            start_date, end_date
        )

        # Revenue by account
        rev_result = await db.execute(
            select(
                Account.name_en,
                func.coalesce(func.sum(JournalLine.base_credit), 0).label("amount"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
                Account.type == "revenue",
            )
            .group_by(Account.name_en)
        )
        revenue = [{"account": r[0], "amount": float(r[1])} for r in rev_result.all()]
        total_revenue = sum(r["amount"] for r in revenue)

        # Expenses by account
        exp_result = await db.execute(
            select(
                Account.name_en,
                func.coalesce(func.sum(JournalLine.base_debit), 0).label("amount"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
                Account.type == "expense",
            )
            .group_by(Account.name_en)
        )
        expenses = [{"account": e[0], "amount": float(e[1])} for e in exp_result.all()]
        total_expenses = sum(e["amount"] for e in expenses)

        return PnLResponse(
            base_currency=await ReportService._base_currency(db, company_id),
            period=ReportService._period_label(
                period_start, period_end, is_default
            ),
            revenue=revenue,
            expenses=expenses,
            net_income=ReportService._net_income(total_revenue, total_expenses),
        )

    @staticmethod
    async def get_cash_flow(
        db: AsyncSession,
        company_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> CashFlowResponse:
        period_start, period_end, is_default = ReportService._period(
            start_date, end_date
        )

        flow_result = await db.execute(
            select(
                func.coalesce(func.sum(JournalLine.base_debit), 0),
                func.coalesce(func.sum(JournalLine.base_credit), 0),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
                Account.is_payment_account,
            )
        )
        inflows, outflows = flow_result.one()
        inflows = float(inflows or 0)
        outflows = float(outflows or 0)
        net = inflows - outflows

        return CashFlowResponse(
            base_currency=await ReportService._base_currency(db, company_id),
            period=ReportService._period_label(
                period_start, period_end, is_default
            ),
            operating=net,
            investing=0,
            financing=0,
            net=net,
            monthly_data=[
                {
                    "month": ReportService._period_label(
                        period_start, period_end, is_default
                    ),
                    "income": inflows,
                    "expenses": outflows,
                    "net": net,
                }
            ],
        )

    @staticmethod
    async def get_balance_sheet(
        db: AsyncSession,
        company_id: str,
        as_of: date | None = None,
    ) -> BalanceSheetResponse:
        report_date = as_of or datetime.now(timezone.utc).date()

        # Compute balances per account type from posted entries
        result = await db.execute(
            select(
                Account.type,
                Account.name_en,
                func.coalesce(func.sum(JournalLine.base_debit), 0).label("debit"),
                func.coalesce(func.sum(JournalLine.base_credit), 0).label("credit"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date <= report_date,
            )
            .group_by(Account.type, Account.name_en)
        )
        rows = result.all()

        assets, liabilities, equity = [], [], []
        cumulative_revenue = 0.0
        cumulative_expenses = 0.0
        for acc_type, name, debit, credit in rows:
            amount = (
                float(debit) - float(credit)
                if acc_type in ("asset", "expense")
                else float(credit) - float(debit)
            )
            entry = {"account": name, "amount": amount}
            if acc_type == "asset":
                assets.append(entry)
            elif acc_type == "liability":
                liabilities.append(entry)
            elif acc_type == "equity":
                equity.append(entry)
            elif acc_type == "revenue":
                cumulative_revenue += float(credit) - float(debit)
            elif acc_type == "expense":
                cumulative_expenses += float(debit) - float(credit)

        current_earnings = ReportService._net_income(
            cumulative_revenue, cumulative_expenses
        )
        equity.append({"account": "Current Earnings", "amount": current_earnings})

        total_assets = sum(a["amount"] for a in assets)
        total_liabilities = sum(liab["amount"] for liab in liabilities)
        total_equity = sum(e["amount"] for e in equity)

        return BalanceSheetResponse(
            base_currency=await ReportService._base_currency(db, company_id),
            as_of=report_date.isoformat(),
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        )

    @staticmethod
    async def get_expenses_by_category(
        db: AsyncSession,
        company_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ExpenseByCategoryResponse:
        period_start, period_end, is_default = ReportService._period(
            start_date, end_date
        )

        result = await db.execute(
            select(
                Account.name_en,
                func.coalesce(func.sum(JournalLine.base_debit), 0).label("amount"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
                Account.type == "expense",
            )
            .group_by(Account.name_en)
        )
        categories = [{"category": r[0], "amount": float(r[1])} for r in result.all()]
        total = sum(c["amount"] for c in categories)

        return ExpenseByCategoryResponse(
            base_currency=await ReportService._base_currency(db, company_id),
            period=ReportService._period_label(
                period_start, period_end, is_default
            ),
            categories=categories,
            total=total,
        )

    @staticmethod
    async def get_vendors(db: AsyncSession, company_id: str) -> VendorReportResponse:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(
                Vendor.name,
                func.coalesce(func.sum(DraftTransaction.amount), 0).label("total"),
            )
            .join(DraftTransaction, DraftTransaction.vendor_id == Vendor.id)
            .where(
                Vendor.company_id == company_id,
                Vendor.is_active,
                DraftTransaction.status == "posted",
                DraftTransaction.transaction_date >= month_start.date(),
            )
            .group_by(Vendor.name)
        )
        vendors = [{"vendor": r[0], "amount": float(r[1])} for r in result.all()]
        total = sum(v["amount"] for v in vendors)

        return VendorReportResponse(
            period=month_start.strftime("%Y-%m"),
            vendors=vendors,
            total=total,
        )

    @staticmethod
    async def get_budget_vs_actual(
        db: AsyncSession, company_id: str
    ) -> BudgetVsActualResponse:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get active budgets
        budget_result = await db.execute(
            select(Budget).where(
                Budget.company_id == company_id,
                Budget.status == "active",
            )
        )
        budget = budget_result.scalar_one_or_none()

        if not budget:
            return BudgetVsActualResponse(
                period=month_start.strftime("%Y-%m"), items=[]
            )

        # Get budget lines
        lines_result = await db.execute(
            select(BudgetLine, Account.name_en)
            .join(Account, BudgetLine.account_id == Account.id)
            .where(BudgetLine.budget_id == str(budget.id))
        )
        items = []
        for line, account_name in lines_result.all():
            # Get actual spending for this account
            actual_result = await db.execute(
                select(func.coalesce(func.sum(JournalLine.base_debit), 0))
                .select_from(JournalLine)
                .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
                .where(
                    JournalEntry.company_id == company_id,
                    JournalEntry.status == "posted",
                    JournalEntry.entry_date >= month_start.date(),
                    JournalLine.account_id == str(line.account_id),
                )
            )
            actual = float(actual_result.scalar() or 0)
            planned = float(line.planned_amount)
            percentage_used = (actual / planned * 100) if planned > 0 else 0

            items.append(
                {
                    "account": account_name,
                    "planned": planned,
                    "actual": actual,
                    "remaining": planned - actual,
                    "percentage_used": percentage_used,
                    "alert": percentage_used >= float(line.alert_percentage),
                }
            )

        return BudgetVsActualResponse(period=month_start.strftime("%Y-%m"), items=items)
