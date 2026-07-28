from decimal import Decimal

import httpx
import pytest

from app.services.currency import LiveExchangeRateError, fetch_live_exchange_rate


@pytest.mark.asyncio
async def test_live_provider_rate_uses_project_conversion_convention():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/latest/USD")
        return httpx.Response(
            200,
            json={
                "result": "success",
                "base_code": "USD",
                "rates": {"EGP": 51.32571, "SAR": 3.75},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rate = await fetch_live_exchange_rate("EGP", "USD", client=client)

    assert rate == Decimal("51.32571")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"result": "error"}),
        httpx.Response(
            200,
            json={"result": "success", "base_code": "USD", "rates": {}},
        ),
    ],
)
async def test_live_provider_errors_are_normalized(response):
    async def handler(request: httpx.Request) -> httpx.Response:
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LiveExchangeRateError):
            await fetch_live_exchange_rate("EGP", "USD", client=client)
