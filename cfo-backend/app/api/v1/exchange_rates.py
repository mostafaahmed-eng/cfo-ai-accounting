from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from app.database import get_db
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateResponse
from app.dependencies import get_current_user, get_current_company_id

router = APIRouter()


@router.get("", response_model=list[ExchangeRateResponse])
async def list_rates(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.company_id == company_id)
        .order_by(ExchangeRate.rate_date.desc())
    )
    return [ExchangeRateResponse.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=ExchangeRateResponse)
async def create_rate(
    data: ExchangeRateCreate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    rate = ExchangeRate(
        id=uuid4(),
        company_id=company_id,
        base_currency=data.base_currency,
        quote_currency=data.quote_currency,
        rate=data.rate,
        rate_date=data.rate_date,
        source=data.source,
    )
    db.add(rate)
    await db.flush()
    return ExchangeRateResponse.model_validate(rate)
