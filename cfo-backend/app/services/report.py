from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from app.models.journal import JournalEntry, JournalLine
from app.models.account import Account
from app.models.approval import ApprovalRequest
from app.models.draft_transaction import DraftTransaction
from app.models.vendor import Vendor
from app.models.budget import Budget, BudgetLine
from app.schemas.report import (
    DashboardResponse,
    PnLResponse,
    CashFlowResponse,
    BalanceSheetResponse,
    ExpenseByCategoryResponse,
    VendorReportResponse,
    BudgetVsActualResponse,
)


class ReportService:
    @staticmethod
    async def get_dashboard(db: AsyncSession, company_id: str) -> DashboardResponse:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Monthly income: sum of credit on revenue accounts from posted entries
        income_result = await db.execute(
            select(func.coalesce(func.sum(JournalLine.credit), 0))
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= month_start.date(),
                Account.type == "revenue",
            )
        )
        monthly_income = float(income_result.scalar() or 0)

        # Monthly expenses: sum of debit on expense accounts from posted entries
        expense_result = await db.execute(
            select(func.coalesce(func.sum(JournalLine.debit), 0))
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= month_start.date(),
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
                    "status": tx.status,
                }
            )

        return DashboardResponse(
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            net_cash_flow=monthly_income - monthly_expenses,
            pending_approvals=pending_approvals,
            recent_transactions=recent_txns,
            budget_warnings=[],
        )

    @staticmethod
    async def get_profit_and_loss(db: AsyncSession, company_id: str) -> PnLResponse:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Revenue by account
        rev_result = await db.execute(
            select(
                Account.name_en,
                func.coalesce(func.sum(JournalLine.credit), 0).label("amount"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= month_start.date(),
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
                func.coalesce(func.sum(JournalLine.debit), 0).label("amount"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= month_start.date(),
                Account.type == "expense",
            )
            .group_by(Account.name_en)
        )
        expenses = [{"account": e[0], "amount": float(e[1])} for e in exp_result.all()]
        total_expenses = sum(e["amount"] for e in expenses)

        return PnLResponse(
            period=month_start.strftime("%Y-%m"),
            revenue=revenue,
            expenses=expenses,
            net_income=total_revenue - total_expenses,
        )

    @staticmethod
    async def get_cash_flow(db: AsyncSession, company_id: str) -> CashFlowResponse:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Net from all posted entries
        net_result = await db.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit), 0)
                - func.coalesce(func.sum(JournalLine.credit), 0)
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= month_start.date(),
            )
        )
        net = float(net_result.scalar() or 0)

        return CashFlowResponse(
            period=month_start.strftime("%Y-%m"),
            operating=net,
            investing=0,
            financing=0,
            net=net,
            monthly_data=[],
        )

    @staticmethod
    async def get_balance_sheet(
        db: AsyncSession, company_id: str
    ) -> BalanceSheetResponse:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Compute balances per account type from posted entries
        result = await db.execute(
            select(
                Account.type,
                Account.name_en,
                func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
                func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
            )
            .group_by(Account.type, Account.name_en)
        )
        rows = result.all()

        assets, liabilities, equity = [], [], []
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

        total_assets = sum(a["amount"] for a in assets)
        total_liabilities = sum(liab["amount"] for liab in liabilities)
        total_equity = sum(e["amount"] for e in equity)

        return BalanceSheetResponse(
            as_of=now.strftime("%Y-%m-%d"),
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        )

    @staticmethod
    async def get_expenses_by_category(
        db: AsyncSession, company_id: str
    ) -> ExpenseByCategoryResponse:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(
                Account.name_en,
                func.coalesce(func.sum(JournalLine.debit), 0).label("amount"),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == "posted",
                JournalEntry.entry_date >= month_start.date(),
                Account.type == "expense",
            )
            .group_by(Account.name_en)
        )
        categories = [{"category": r[0], "amount": float(r[1])} for r in result.all()]
        total = sum(c["amount"] for c in categories)

        return ExpenseByCategoryResponse(
            period=month_start.strftime("%Y-%m"),
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
                select(func.coalesce(func.sum(JournalLine.debit), 0))
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
