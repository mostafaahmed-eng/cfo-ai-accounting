from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.journal import JournalEntry, JournalLine
from app.models.draft_transaction import DraftTransaction


async def get_next_entry_number(db: AsyncSession, company_id: str) -> str:
    result = await db.execute(
        select(func.count())
        .select_from(JournalEntry)
        .where(JournalEntry.company_id == company_id)
    )
    count = result.scalar() or 0
    return f"JE-{count + 1:06d}"


async def create_journal_entry_from_draft(
    db: AsyncSession, draft: DraftTransaction
) -> JournalEntry:
    entry_number = await get_next_entry_number(db, draft.company_id)

    expense_account_id = (
        draft.category_account_id if draft.category_account_id else uuid4()
    )
    payment_account_id = (
        draft.payment_account_id if draft.payment_account_id else uuid4()
    )

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
        posted_at=datetime.utcnow(),
    )
    db.add(journal_entry)
    await db.flush()

    base_amount = float(draft.amount)

    if draft.type == "expense":
        debit_line = JournalLine(
            id=uuid4(),
            journal_entry_id=str(journal_entry.id),
            account_id=str(expense_account_id),
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
            account_id=str(payment_account_id),
            description=draft.description,
            debit=0,
            credit=base_amount,
            currency=draft.currency,
            base_debit=0,
            base_credit=base_amount,
        )
    elif draft.type == "income":
        debit_line = JournalLine(
            id=uuid4(),
            journal_entry_id=str(journal_entry.id),
            account_id=str(payment_account_id),
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
            account_id=str(expense_account_id),
            description=draft.description,
            debit=0,
            credit=base_amount,
            currency=draft.currency,
            base_debit=0,
            base_credit=base_amount,
        )
    else:
        debit_line = JournalLine(
            id=uuid4(),
            journal_entry_id=str(journal_entry.id),
            account_id=str(payment_account_id),
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
            account_id=str(expense_account_id),
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

    return journal_entry
