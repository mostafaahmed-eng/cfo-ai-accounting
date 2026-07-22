from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.journal import JournalEntry
from app.models.user import User
from app.schemas.journal import JournalEntryResponse
from app.dependencies import get_current_user, get_current_company_id

router = APIRouter()


@router.get("", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JournalEntry)
        .where(JournalEntry.company_id == company_id)
        .order_by(JournalEntry.created_at.desc())
    )
    entries = result.scalars().all()
    response = []
    for entry in entries:
        await db.refresh(entry, ["lines"])
        entry_data = JournalEntryResponse.model_validate(entry)
        entry_data.lines = entry.lines
        response.append(entry_data)
    return response


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.id == entry_id, JournalEntry.company_id == company_id
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    await db.refresh(entry, ["lines"])
    entry_data = JournalEntryResponse.model_validate(entry)
    entry_data.lines = entry.lines
    return entry_data
