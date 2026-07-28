from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.draft_transaction import DraftTransaction
from app.models.exchange_rate import ExchangeRate
from app.models.journal import JournalEntry, JournalLine
from app.services.currency import LiveExchangeRateError


def _account(company_id, code: str, account_type: str, *, payment: bool = False):
    return Account(
        id=uuid4(),
        company_id=company_id,
        code=code,
        name_en=f"Currency test {code}",
        type=account_type,
        subtype="test",
        is_payment_account=payment,
        is_active=True,
    )


def _draft(company_id, transaction_type: str, amount: float, currency: str):
    return DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        type=transaction_type,
        amount=amount,
        tax_amount=0,
        currency=currency,
        transaction_date=datetime.now(UTC).date(),
        description=f"{currency} {transaction_type}",
        status="ready_for_review",
    )


async def _approve(client, headers, draft, category, payment):
    update = await client.patch(
        f"/api/v1/draft-transactions/{draft.id}",
        json={
            "category_account_id": str(category.id),
            "payment_account_id": str(payment.id),
        },
        headers=headers,
    )
    assert update.status_code == 200
    return await client.post(
        f"/api/v1/draft-transactions/{draft.id}/approve",
        headers=headers,
    )


@pytest.mark.asyncio
async def test_non_base_currency_posts_converted_base_lines(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    expense = _account(company_id, "FX-EXP", "expense")
    cash = _account(company_id, "FX-CASH", "asset", payment=True)
    draft = _draft(company_id, "expense", 50, "EUR")
    rate = ExchangeRate(
        id=uuid4(),
        company_id=company_id,
        base_currency="USD",
        quote_currency="EUR",
        rate=1.2,
        rate_date=draft.transaction_date,
        source="manual-test",
    )
    db_session.add_all([expense, cash, draft, rate])
    await db_session.flush()

    approved = await _approve(client, headers, draft, expense, cash)
    assert approved.status_code == 200

    entry = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_id == str(draft.id))
        )
    ).scalar_one()
    lines = (
        (
            await db_session.execute(
                select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
            )
        )
        .scalars()
        .all()
    )
    assert float(entry.exchange_rate) == pytest.approx(1.2)
    assert sum(float(line.debit) for line in lines) == pytest.approx(50)
    assert sum(float(line.credit) for line in lines) == pytest.approx(50)
    assert sum(float(line.base_debit) for line in lines) == pytest.approx(60)
    assert sum(float(line.base_credit) for line in lines) == pytest.approx(60)


@pytest.mark.asyncio
async def test_missing_exchange_rate_rejects_posting_safely(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    expense = _account(company_id, "NOFX-EXP", "expense")
    cash = _account(company_id, "NOFX-CASH", "asset", payment=True)
    draft = _draft(company_id, "expense", 50, "EUR")
    draft.transaction_date -= timedelta(days=10)
    db_session.add_all([expense, cash, draft])
    await db_session.flush()

    approved = await _approve(client, headers, draft, expense, cash)
    assert approved.status_code == 400
    assert "No EUR to USD exchange rate" in approved.json()["detail"]
    await db_session.refresh(draft)
    assert draft.status == "ready_for_review"
    assert draft.approved_by is None
    assert draft.approved_at is None
    entry = await db_session.execute(
        select(JournalEntry).where(JournalEntry.source_id == str(draft.id))
    )
    assert entry.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_current_rate_is_fetched_stored_and_reused(
    client, db_session, _setup_company_and_user, monkeypatch
):
    company_id, _, headers = _setup_company_and_user
    expense = _account(company_id, "LIVEFX-EXP", "expense")
    cash = _account(company_id, "LIVEFX-CASH", "asset", payment=True)
    first_draft = _draft(company_id, "expense", 10, "EUR")
    second_draft = _draft(company_id, "expense", 5, "EUR")
    calls = 0

    async def fake_fetch(base_currency: str, quote_currency: str):
        nonlocal calls
        calls += 1
        assert base_currency == "USD"
        assert quote_currency == "EUR"
        return Decimal("1.23456789")

    monkeypatch.setattr("app.services.currency.fetch_live_exchange_rate", fake_fetch)
    db_session.add_all([expense, cash, first_draft, second_draft])
    await db_session.flush()

    assert (
        await _approve(client, headers, first_draft, expense, cash)
    ).status_code == 200
    assert (
        await _approve(client, headers, second_draft, expense, cash)
    ).status_code == 200
    assert calls == 1

    stored_rate = (
        await db_session.execute(
            select(ExchangeRate).where(
                ExchangeRate.company_id == company_id,
                ExchangeRate.base_currency == "USD",
                ExchangeRate.quote_currency == "EUR",
                ExchangeRate.rate_date == first_draft.transaction_date,
            )
        )
    ).scalar_one()
    assert float(stored_rate.rate) == pytest.approx(1.23456789)
    assert stored_rate.source == "open.er-api.com"
    assert stored_rate.created_at.date() == datetime.now(UTC).date()

    entries = (
        (
            await db_session.execute(
                select(JournalEntry)
                .where(
                    JournalEntry.source_id.in_(
                        [str(first_draft.id), str(second_draft.id)]
                    )
                )
                .order_by(JournalEntry.source_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 2
    assert all(
        float(entry.exchange_rate) == pytest.approx(1.23456789) for entry in entries
    )

    first_lines = (
        (
            await db_session.execute(
                select(JournalLine).where(JournalLine.journal_entry_id == entries[0].id)
            )
        )
        .scalars()
        .all()
    )
    expected_base = (
        Decimal(str(first_lines[0].debit or first_lines[0].credit))
        * Decimal("1.23456789")
    ).quantize(Decimal("0.0001"))
    assert sum(Decimal(line.base_debit) for line in first_lines) == expected_base
    assert sum(Decimal(line.base_credit) for line in first_lines) == expected_base


@pytest.mark.asyncio
async def test_live_rate_provider_failure_requires_manual_rate(
    client, db_session, _setup_company_and_user, monkeypatch
):
    company_id, _, headers = _setup_company_and_user
    expense = _account(company_id, "FAILFX-EXP", "expense")
    cash = _account(company_id, "FAILFX-CASH", "asset", payment=True)
    draft = _draft(company_id, "expense", 10, "GBP")

    async def failing_fetch(base_currency: str, quote_currency: str):
        raise LiveExchangeRateError("provider timeout")

    monkeypatch.setattr("app.services.currency.fetch_live_exchange_rate", failing_fetch)
    db_session.add_all([expense, cash, draft])
    await db_session.flush()

    response = await _approve(client, headers, draft, expense, cash)
    assert response.status_code == 400
    assert "add a manual rate" in response.json()["detail"]

    rate = await db_session.execute(
        select(ExchangeRate).where(
            ExchangeRate.company_id == company_id,
            ExchangeRate.quote_currency == "GBP",
        )
    )
    assert rate.scalar_one_or_none() is None
    entry = await db_session.execute(
        select(JournalEntry).where(JournalEntry.source_id == str(draft.id))
    )
    assert entry.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_dashboard_and_breakdowns_use_base_currency(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    revenue = _account(company_id, "MIX-REV", "revenue")
    expense = _account(company_id, "MIX-EXP", "expense")
    cash = _account(company_id, "MIX-CASH", "asset", payment=True)
    income_draft = _draft(company_id, "income", 100, "USD")
    expense_draft = _draft(company_id, "expense", 50, "EUR")
    rate = ExchangeRate(
        id=uuid4(),
        company_id=company_id,
        base_currency="USD",
        quote_currency="EUR",
        rate=1.2,
        rate_date=expense_draft.transaction_date,
        source="manual-test",
    )
    db_session.add_all([revenue, expense, cash, income_draft, expense_draft, rate])
    await db_session.flush()

    assert (
        await _approve(client, headers, income_draft, revenue, cash)
    ).status_code == 200
    assert (
        await _approve(client, headers, expense_draft, expense, cash)
    ).status_code == 200

    dashboard = (await client.get("/api/v1/reports/dashboard", headers=headers)).json()
    assert dashboard["base_currency"] == "USD"
    assert dashboard["monthly_income"] == pytest.approx(100)
    assert dashboard["monthly_expenses"] == pytest.approx(60)
    assert dashboard["net_cash_flow"] == pytest.approx(40)

    cash_flow = (await client.get("/api/v1/reports/cash-flow", headers=headers)).json()
    assert cash_flow["base_currency"] == "USD"
    assert cash_flow["operating"] == pytest.approx(40)
    assert cash_flow["net"] == pytest.approx(40)
    assert cash_flow["monthly_data"][0]["income"] == pytest.approx(100)
    assert cash_flow["monthly_data"][0]["expenses"] == pytest.approx(60)

    categories = (
        await client.get("/api/v1/reports/expenses-by-category", headers=headers)
    ).json()
    assert categories["base_currency"] == "USD"
    assert categories["total"] == pytest.approx(60)
    assert categories["categories"] == [
        {"category": expense.name_en, "amount": pytest.approx(60)}
    ]


@pytest.mark.asyncio
async def test_balance_sheet_includes_cumulative_earnings_across_currencies(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    revenue_usd = _account(company_id, "BS-REV-USD", "revenue")
    revenue_eur = _account(company_id, "BS-REV-EUR", "revenue")
    expense_eur = _account(company_id, "BS-EXP-EUR", "expense")
    expense_usd = _account(company_id, "BS-EXP-USD", "expense")
    cash = _account(company_id, "BS-CASH", "asset", payment=True)
    income_usd = _draft(company_id, "income", 100, "USD")
    income_eur = _draft(company_id, "income", 50, "EUR")
    cost_eur = _draft(company_id, "expense", 25, "EUR")
    cost_usd = _draft(company_id, "expense", 10, "USD")
    rate = ExchangeRate(
        id=uuid4(),
        company_id=company_id,
        base_currency="USD",
        quote_currency="EUR",
        rate=1.2,
        rate_date=income_eur.transaction_date,
        source="manual-test",
    )
    db_session.add_all(
        [
            revenue_usd,
            revenue_eur,
            expense_eur,
            expense_usd,
            cash,
            income_usd,
            income_eur,
            cost_eur,
            cost_usd,
            rate,
        ]
    )
    await db_session.flush()

    assert (
        await _approve(client, headers, income_usd, revenue_usd, cash)
    ).status_code == 200
    assert (
        await _approve(client, headers, income_eur, revenue_eur, cash)
    ).status_code == 200
    assert (
        await _approve(client, headers, cost_eur, expense_eur, cash)
    ).status_code == 200
    assert (
        await _approve(client, headers, cost_usd, expense_usd, cash)
    ).status_code == 200

    response = await client.get("/api/v1/reports/balance-sheet", headers=headers)
    assert response.status_code == 200
    balance_sheet = response.json()
    current_earnings = next(
        item
        for item in balance_sheet["equity"]
        if item["account"] == "Current Earnings"
    )

    # USD 100 + (EUR 50 * 1.2) - (EUR 25 * 1.2) - USD 10 = USD 120.
    assert current_earnings["amount"] == pytest.approx(120)
    assert balance_sheet["total_assets"] == pytest.approx(120)
    assert balance_sheet["total_liabilities"] == pytest.approx(0)
    assert balance_sheet["total_equity"] == pytest.approx(120)
    assert balance_sheet["total_assets"] == pytest.approx(
        balance_sheet["total_liabilities"] + balance_sheet["total_equity"]
    )


@pytest.mark.asyncio
async def test_report_date_filters_and_default_period_are_backward_compatible(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    revenue = _account(company_id, "DATE-REV", "revenue")
    expense = _account(company_id, "DATE-EXP", "expense")
    cash = _account(company_id, "DATE-CASH", "asset", payment=True)
    income = _draft(company_id, "income", 1000, "USD")
    early_expense = _draft(company_id, "expense", 100, "USD")
    late_expense = _draft(company_id, "expense", 50, "USD")
    today = datetime.now(UTC).date()
    income.transaction_date = today.replace(day=5)
    early_expense.transaction_date = today.replace(day=15)
    late_expense.transaction_date = today.replace(day=25)
    db_session.add_all([revenue, expense, cash, income, early_expense, late_expense])
    await db_session.flush()

    assert (await _approve(client, headers, income, revenue, cash)).status_code == 200
    assert (
        await _approve(client, headers, early_expense, expense, cash)
    ).status_code == 200
    assert (
        await _approve(client, headers, late_expense, expense, cash)
    ).status_code == 200

    income_only_params = {
        "start_date": income.transaction_date.isoformat(),
        "end_date": income.transaction_date.isoformat(),
    }
    dashboard = (
        await client.get(
            "/api/v1/reports/dashboard",
            params=income_only_params,
            headers=headers,
        )
    ).json()
    assert dashboard["monthly_income"] == pytest.approx(1000)
    assert dashboard["monthly_expenses"] == pytest.approx(0)
    assert dashboard["net_cash_flow"] == pytest.approx(1000)

    pnl = (
        await client.get(
            "/api/v1/reports/profit-and-loss",
            params=income_only_params,
            headers=headers,
        )
    ).json()
    assert pnl["net_income"] == pytest.approx(1000)

    cash_flow = (
        await client.get(
            "/api/v1/reports/cash-flow",
            params=income_only_params,
            headers=headers,
        )
    ).json()
    assert cash_flow["net"] == pytest.approx(1000)

    categories = (
        await client.get(
            "/api/v1/reports/expenses-by-category",
            params=income_only_params,
            headers=headers,
        )
    ).json()
    assert categories["categories"] == []
    assert categories["total"] == pytest.approx(0)

    month_params = {
        "start_date": today.replace(day=1).isoformat(),
        "end_date": today.replace(
            day=monthrange(today.year, today.month)[1]
        ).isoformat(),
    }
    for endpoint in ("dashboard", "profit-and-loss", "cash-flow"):
        default_response = await client.get(
            f"/api/v1/reports/{endpoint}", headers=headers
        )
        explicit_response = await client.get(
            f"/api/v1/reports/{endpoint}",
            params=month_params,
            headers=headers,
        )
        assert default_response.status_code == 200
        assert explicit_response.status_code == 200
        default_data = default_response.json()
        explicit_data = explicit_response.json()
        if endpoint == "dashboard":
            assert default_data["monthly_income"] == explicit_data["monthly_income"]
            assert default_data["monthly_expenses"] == explicit_data["monthly_expenses"]
            assert default_data["net_cash_flow"] == explicit_data["net_cash_flow"]
        elif endpoint == "profit-and-loss":
            assert default_data["net_income"] == explicit_data["net_income"]
        else:
            assert default_data["net"] == explicit_data["net"]

    invalid = await client.get(
        "/api/v1/reports/dashboard",
        params={
            "start_date": late_expense.transaction_date.isoformat(),
            "end_date": income.transaction_date.isoformat(),
        },
        headers=headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "start_date must not be after end_date"


@pytest.mark.asyncio
async def test_balance_sheet_as_of_excludes_later_entries(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    revenue = _account(company_id, "ASOF-REV", "revenue")
    expense = _account(company_id, "ASOF-EXP", "expense")
    cash = _account(company_id, "ASOF-CASH", "asset", payment=True)
    income = _draft(company_id, "income", 1000, "USD")
    expense_draft = _draft(company_id, "expense", 250, "USD")
    today = datetime.now(UTC).date()
    income.transaction_date = today.replace(day=5)
    expense_draft.transaction_date = today.replace(day=20)
    db_session.add_all([revenue, expense, cash, income, expense_draft])
    await db_session.flush()

    assert (await _approve(client, headers, income, revenue, cash)).status_code == 200
    assert (
        await _approve(client, headers, expense_draft, expense, cash)
    ).status_code == 200

    before_expense = (
        await client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of": income.transaction_date.isoformat()},
            headers=headers,
        )
    ).json()
    after_expense = (
        await client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of": expense_draft.transaction_date.isoformat()},
            headers=headers,
        )
    ).json()

    assert before_expense["total_assets"] == pytest.approx(1000)
    assert before_expense["total_equity"] == pytest.approx(1000)
    assert after_expense["total_assets"] == pytest.approx(750)
    assert after_expense["total_equity"] == pytest.approx(750)
