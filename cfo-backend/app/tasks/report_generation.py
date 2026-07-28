import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.services.report import ReportService
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


async def _generate(company_id: str, year: int, month: int) -> dict:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        dashboard = await ReportService.get_dashboard(session, company_id)
        pnl = await ReportService.get_profit_and_loss(session, company_id)
        cash_flow = await ReportService.get_cash_flow(session, company_id)
        balance_sheet = await ReportService.get_balance_sheet(session, company_id)

        return {
            "status": "ok",
            "company_id": company_id,
            "year": year,
            "month": month,
            "dashboard": dashboard.model_dump(),
            "profit_and_loss": pnl.model_dump(),
            "cash_flow": cash_flow.model_dump(),
            "balance_sheet": balance_sheet.model_dump(),
        }


@celery_app.task(bind=True, max_retries=2)
def generate_monthly_report(self, company_id: str, year: int, month: int):
    try:
        return _run_async(_generate(company_id, year, month))
    except Exception as exc:
        logger.exception(
            "Report generation failed for company %s %d-%02d", company_id, year, month
        )
        self.retry(exc=exc)
