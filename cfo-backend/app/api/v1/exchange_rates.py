from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.company import Company
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateResponse
from app.schemas.pagination import PageParams, get_page_params

router = APIRouter()


@router.get("", response_model=list[ExchangeRateResponse])
async def list_rates(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
):
    filters = (ExchangeRate.company_id == company_id,)
    total = await db.scalar(
        select(func.count()).select_from(ExchangeRate).where(*filters)
    )
    result = await db.execute(
        select(ExchangeRate)
        .where(*filters)
        .order_by(ExchangeRate.rate_date.desc())
        .offset(page.offset)
        .limit(page.limit)
    )
    response.headers["X-Total-Count"] = str(total)
    return [ExchangeRateResponse.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=ExchangeRateResponse)
async def create_rate(
    data: ExchangeRateCreate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if data.base_currency != company.base_currency.upper():
        raise HTTPException(
            status_code=400,
            detail=f"Base currency must match company base currency {company.base_currency}",
        )
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
