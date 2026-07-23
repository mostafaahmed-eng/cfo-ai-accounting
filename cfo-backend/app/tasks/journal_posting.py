import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.models.journal import JournalEntry

logger = logging.getLogger(__name__)
settings = get_settings()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL, pool_size=2, max_overflow=2)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _post(journal_entry_id: str) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(JournalEntry).where(JournalEntry.id == journal_entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return {"status": "error", "message": "Journal entry not found"}

        await session.refresh(entry, ["lines"])

        if entry.status == "posted":
            return {"status": "ok", "message": "Already posted"}

        total_debit = sum(float(line.debit) for line in entry.lines)
        total_credit = sum(float(line.credit) for line in entry.lines)

        if abs(total_debit - total_credit) > 0.01:
            entry.status = "draft"
            await session.commit()
            return {
                "status": "error",
                "message": f"Unbalanced entry: debit={total_debit}, credit={total_credit}",
            }

        for line in entry.lines:
            if float(line.debit) < 0 or float(line.credit) < 0:
                entry.status = "draft"
                await session.commit()
                return {
                    "status": "error",
                    "message": "Negative debit or credit not allowed",
                }

        from datetime import datetime, timezone

        entry.status = "posted"
        entry.posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

        return {"status": "ok", "entry_id": journal_entry_id}


@celery_app.task(bind=True, max_retries=2)
def post_journal_entry(self, journal_entry_id: str):
    try:
        return _run_async(_post(journal_entry_id))
    except Exception as exc:
        logger.exception("Journal posting failed for entry %s", journal_entry_id)
        self.retry(exc=exc)
