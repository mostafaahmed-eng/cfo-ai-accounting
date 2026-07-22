from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from app.models.exchange_rate import ExchangeRate


async def get_exchange_rate(db: AsyncSession, company_id: str, base_currency: str, quote_currency: str, on_date: date | None = None) -> Decimal:
    if base_currency == quote_currency:
        return Decimal("1.0")

    query = select(ExchangeRate).where(
        ExchangeRate.company_id == company_id,
        ExchangeRate.base_currency == base_currency,
        ExchangeRate.quote_currency == quote_currency,
    )
    if on_date:
        query = query.where(ExchangeRate.rate_date <= on_date)
    query = query.order_by(ExchangeRate.rate_date.desc()).limit(1)

    result = await db.execute(query)
    rate = result.scalar_one_or_none()
    if rate:
        return rate.rate
    return Decimal("1.0")
