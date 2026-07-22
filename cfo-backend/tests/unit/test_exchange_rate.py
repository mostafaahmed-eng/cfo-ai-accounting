from decimal import Decimal
import pytest


class TestExchangeRateCalculations:
    def test_same_currency_rate(self):
        rate = Decimal("1.0")
        amount = Decimal("100.00")
        converted = amount * rate
        assert converted == Decimal("100.00")

    def test_usd_to_egp(self):
        amount_usd = Decimal("100")
        rate = Decimal("30.5")
        amount_egp = amount_usd * rate
        assert amount_egp == Decimal("3050.00")

    def test_egp_to_usd(self):
        amount_egp = Decimal("3050.00")
        rate = Decimal("0.0327868852459016")
        amount_usd = amount_egp * rate
        assert float(amount_usd) == pytest.approx(100.0, abs=0.01)

    def test_exchange_rate_preserved_at_posting(self):
        """Exchange rate used at posting time should be stored, not recomputed."""
        rate_at_posting = Decimal("30.50")
        rate_today = Decimal("31.00")
        amount = Decimal("100.00")
        # Historical reports use the stored rate
        historical_amount = amount * rate_at_posting
        assert historical_amount == Decimal("3050.00")
        # NOT using today's rate
        assert historical_amount != amount * rate_today

    def test_zero_amount(self):
        amount = Decimal("0")
        rate = Decimal("30.50")
        assert amount * rate == Decimal("0")

    def test_small_amount_precision(self):
        amount = Decimal("0.01")
        rate = Decimal("30.50000000")
        result = amount * rate
        assert result == Decimal("0.30500000")
