import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_exchange_rates_company_id_fk_present(_engine):
    """Regression guard: exchange_rates.company_id must reference companies.id.

    The authoritative proof that the forward-only migration (010) builds it on
    a real database comes from the alembic empty-DB -> head run; this test
    keeps the constraint from silently regressing via metadata drift.
    """
    async with _engine.connect() as conn:
        fks = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_foreign_keys("exchange_rates")
        )

    assert fks, "exchange_rates has no foreign keys"
    assert any(
        fk.get("referred_table") == "companies"
        and fk.get("constrained_columns") == ["company_id"]
        for fk in fks
    ), f"company_id FK to companies missing; found: {fks}"
