from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.journal import JournalEntry
from app.models.user import User
from app.schemas.journal import JournalEntryResponse
from app.schemas.pagination import PageParams, get_page_params

router = APIRouter()


@router.get("", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
):
    filters = (JournalEntry.company_id == company_id,)
    total = await db.scalar(
        select(func.count()).select_from(JournalEntry).where(*filters)
    )
    result = await db.execute(
        select(JournalEntry)
        .where(*filters)
        .order_by(JournalEntry.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
    )
    entries = result.scalars().all()
    response.headers["X-Total-Count"] = str(total)
    result_entries = []
    for entry in entries:
        await db.refresh(entry, ["lines"])
        entry_data = JournalEntryResponse.model_validate(entry)
        entry_data.lines = entry.lines
        result_entries.append(entry_data)
    return result_entries


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
