from app.core.text_processing import extract_currency


class TestUSD:
    def test_symbol(self):
        assert extract_currency("$100") == "USD"

    def test_code(self):
        assert extract_currency("100 USD") == "USD"

    def test_word(self):
        assert extract_currency("100 dollars") == "USD"


class TestEUR:
    def test_symbol(self):
        assert extract_currency("€50") == "EUR"

    def test_code(self):
        assert extract_currency("50 EUR") == "EUR"


class TestGBP:
    def test_symbol(self):
        assert extract_currency("£100") == "GBP"


class TestEGP:
    def test_arabic(self):
        assert extract_currency("100 جنيه") == "EGP"


class TestNoCurrency:
    def test_no_indicators(self):
        assert extract_currency("I bought something") is None

    def test_empty(self):
        assert extract_currency("") is None

    def test_numbers_only(self):
        assert extract_currency("12345") is None
