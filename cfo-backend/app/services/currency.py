from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.base import _utcnow
from app.models.exchange_rate import ExchangeRate

FX_PROVIDER_SOURCE = "open.er-api.com"


class ExchangeRateUnavailableError(ValueError):
    pass


class LiveExchangeRateError(ValueError):
    pass


async def fetch_live_exchange_rate(
    base_currency: str,
    quote_currency: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Decimal:
    """Return base-currency units per one unit of the quote currency."""
    base_currency = base_currency.upper()
    quote_currency = quote_currency.upper()
    settings = get_settings()
    url = f"{settings.FX_PROVIDER_BASE_URL}/latest/{quote_currency}"
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=settings.FX_PROVIDER_TIMEOUT_SECONDS)

    try:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
        if payload.get("result") != "success":
            raise LiveExchangeRateError("FX provider returned an unsuccessful result")
        if payload.get("base_code") != quote_currency:
            raise LiveExchangeRateError("FX provider returned an unexpected base currency")
        raw_rate = payload.get("rates", {}).get(base_currency)
        if raw_rate is None:
            raise LiveExchangeRateError(
                f"FX provider did not return a rate for {base_currency}"
            )
        rate = Decimal(str(raw_rate))
        if rate <= 0:
            raise LiveExchangeRateError("FX provider returned a non-positive rate")
        return rate
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        if isinstance(exc, LiveExchangeRateError):
            raise
        raise LiveExchangeRateError("Live exchange-rate lookup failed") from exc
    finally:
        if owns_client:
            await client.aclose()


async def _stored_exchange_rate(
    db: AsyncSession,
    company_id: str,
    base_currency: str,
    quote_currency: str,
    *,
    exact_date: date | None = None,
    on_or_before: date | None = None,
) -> ExchangeRate | None:
    query = select(ExchangeRate).where(
        ExchangeRate.company_id == company_id,
        ExchangeRate.base_currency == base_currency,
        ExchangeRate.quote_currency == quote_currency,
    )
    if exact_date is not None:
        query = query.where(ExchangeRate.rate_date == exact_date)
    elif on_or_before is not None:
        query = query.where(ExchangeRate.rate_date <= on_or_before)
    query = query.order_by(ExchangeRate.rate_date.desc()).limit(1)
    return (await db.execute(query)).scalar_one_or_none()


async def get_exchange_rate(
    db: AsyncSession,
    company_id: str,
    base_currency: str,
    quote_currency: str,
    on_date: date | None = None,
) -> Decimal:
    base_currency = base_currency.upper()
    quote_currency = quote_currency.upper()
    if base_currency == quote_currency:
        return Decimal("1.0")

    if on_date is not None:
        exact_rate = await _stored_exchange_rate(
            db,
            company_id,
            base_currency,
            quote_currency,
            exact_date=on_date,
        )
        if exact_rate:
            return Decimal(str(exact_rate.rate))

        age_days = (datetime.now(timezone.utc).date() - on_date).days
        settings = get_settings()
        if 0 <= age_days <= settings.FX_AUTO_FETCH_MAX_AGE_DAYS:
            try:
                fetched_rate = await fetch_live_exchange_rate(
                    base_currency, quote_currency
                )
            except LiveExchangeRateError as exc:
                raise ExchangeRateUnavailableError(
                    f"No {quote_currency} to {base_currency} exchange rate is "
                    f"available on {on_date}; add a manual rate"
                ) from exc

            fetched_at = _utcnow()
            statement = (
                insert(ExchangeRate)
                .values(
                    id=uuid4(),
                    company_id=company_id,
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    rate=fetched_rate,
                    rate_date=on_date,
                    source=FX_PROVIDER_SOURCE,
                    created_at=fetched_at,
                    updated_at=fetched_at,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        ExchangeRate.company_id,
                        ExchangeRate.base_currency,
                        ExchangeRate.quote_currency,
                        ExchangeRate.rate_date,
                    ]
                )
            )
            await db.execute(statement)
            stored_rate = await _stored_exchange_rate(
                db,
                company_id,
                base_currency,
                quote_currency,
                exact_date=on_date,
            )
            if stored_rate:
                return Decimal(str(stored_rate.rate))

    rate = await _stored_exchange_rate(
        db,
        company_id,
        base_currency,
        quote_currency,
        on_or_before=on_date,
    )
    if rate:
        return Decimal(str(rate.rate))
    rate_date = f" on or before {on_date}" if on_date else ""
    raise ExchangeRateUnavailableError(
        f"No {quote_currency} to {base_currency} exchange rate is available{rate_date}"
    )
