from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.journal import JournalEntry, JournalLine
from app.models.draft_transaction import DraftTransaction
from app.models.account import Account
from app.models.base import _utcnow


class JournalError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


async def get_next_entry_number(db: AsyncSession, company_id) -> str:
    result = await db.execute(
        select(func.count())
        .select_from(JournalEntry)
        .where(JournalEntry.company_id == company_id)
    )
    count = result.scalar() or 0
    return f"JE-{count + 1:06d}"


async def _validate_account(db: AsyncSession, account_id, company_id) -> Account:
    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.company_id == company_id,
            Account.is_active,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise JournalError(
            f"Account {account_id} not found or not active for this company"
        )
    return account


async def create_journal_entry_from_draft(
    db: AsyncSession, draft: DraftTransaction
) -> JournalEntry:
    if not draft.category_account_id:
        raise JournalError("Category account is required for journal posting")
    if not draft.payment_account_id:
        raise JournalError("Payment account is required for journal posting")

    await _validate_account(db, draft.category_account_id, draft.company_id)
    await _validate_account(db, draft.payment_account_id, draft.company_id)

    entry_number = await get_next_entry_number(db, draft.company_id)

    journal_entry = JournalEntry(
        id=uuid4(),
        company_id=draft.company_id,
        entry_number=entry_number,
        entry_date=draft.transaction_date,
        description=draft.description,
        source_type=draft.type,
        source_id=str(draft.id),
        status="posted",
        currency=draft.currency,
        exchange_rate=1,
        posted_by=draft.approved_by,
        posted_at=_utcnow(),
    )
    db.add(journal_entry)
    await db.flush()

    base_amount = float(draft.amount)

    if draft.type == "expense":
        debit_account_id = str(draft.category_account_id)
        credit_account_id = str(draft.payment_account_id)
    elif draft.type == "income":
        debit_account_id = str(draft.payment_account_id)
        credit_account_id = str(draft.category_account_id)
    else:
        debit_account_id = str(draft.payment_account_id)
        credit_account_id = str(draft.category_account_id)

    debit_line = JournalLine(
        id=uuid4(),
        journal_entry_id=str(journal_entry.id),
        account_id=debit_account_id,
        description=draft.description,
        debit=base_amount,
        credit=0,
        currency=draft.currency,
        base_debit=base_amount,
        base_credit=0,
    )
    credit_line = JournalLine(
        id=uuid4(),
        journal_entry_id=str(journal_entry.id),
        account_id=credit_account_id,
        description=draft.description,
        debit=0,
        credit=base_amount,
        currency=draft.currency,
        base_debit=0,
        base_credit=base_amount,
    )

    db.add(debit_line)
    db.add(credit_line)
    await db.flush()

    total_debit = float(debit_line.debit)
    total_credit = float(credit_line.credit)
    if abs(total_debit - total_credit) > 0.001:
        raise JournalError(
            f"Unbalanced journal entry: debit={total_debit}, credit={total_credit}"
        )

    return journal_entry
