import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.draft_transaction import DraftTransaction
from app.tasks.celery_app import celery_app

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


async def _detect(company_id: str, draft_id: str) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(DraftTransaction).where(DraftTransaction.id == draft_id)
        )
        draft = result.scalar_one_or_none()
        if not draft:
            return {"status": "error", "message": "Draft not found"}

        candidates = await session.execute(
            select(DraftTransaction).where(
                DraftTransaction.company_id == company_id,
                DraftTransaction.id != draft.id,
                DraftTransaction.status.in_(["ready_for_review", "approved", "posted"]),
                DraftTransaction.amount == draft.amount,
                DraftTransaction.type == draft.type,
            )
        )
        duplicates = candidates.scalars().all()

        if duplicates:
            logger.info(
                "Potential duplicates found for draft %s: %s",
                draft_id,
                [str(d.id) for d in duplicates],
            )
            return {
                "status": "possible_duplicate",
                "draft_id": draft_id,
                "duplicate_ids": [str(d.id) for d in duplicates],
                "count": len(duplicates),
            }

        return {"status": "ok", "draft_id": draft_id, "count": 0}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def detect_duplicates(self, company_id: str, draft_transaction_id: str):
    try:
        return _run_async(_detect(company_id, draft_transaction_id))
    except Exception as exc:
        logger.exception(
            "Duplicate detection failed for draft %s", draft_transaction_id
        )
        self.retry(exc=exc)
