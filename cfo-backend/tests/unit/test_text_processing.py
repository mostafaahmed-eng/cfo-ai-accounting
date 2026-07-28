from app.core.text_processing import (
    detect_language,
    extract_amount,
    extract_currency,
    normalize_arabic_digits,
)


class TestArabicDigitNormalization:
    def test_arabic_to_western(self):
        assert normalize_arabic_digits("٥٠٠") == "500"

    def test_all_arabic_digits(self):
        assert normalize_arabic_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"

    def test_mixed_text_with_arabic_digits(self):
        result = normalize_arabic_digits("Price is ٥٠٠ dollars")
        assert result == "Price is 500 dollars"

    def test_no_arabic_digits(self):
        assert normalize_arabic_digits("hello world") == "hello world"

    def test_empty_string(self):
        assert normalize_arabic_digits("") == ""

    def test_pure_arabic_number(self):
        assert normalize_arabic_digits("١٢٣٤٥") == "12345"


class TestLanguageDetection:
    def test_english_text(self):
        assert detect_language("I spent $100 for VPS hosting") == "en"

    def test_arabic_text(self):
        assert detect_language("دفعت ٥٠٠ جنيه إعلانات") == "ar"

    def test_mixed_language(self):
        assert detect_language("Hello مرحبا world عالم") == "mixed"

    def test_empty_string(self):
        assert detect_language("") == "unknown"

    def test_numbers_only(self):
        assert detect_language("12345") == "unknown"

    def test_mostly_english(self):
        assert detect_language("This is English text with a عربي word") == "en"

    def test_mostly_arabic(self):
        assert detect_language("هذا نص عربي مع word") == "ar"

    def test_arabic_expense(self):
        result = detect_language("دفعت مبلغ 500 جنيه لشركة الإعلانات")
        assert result == "ar"


class TestCurrencyDetection:
    def test_usd_symbol(self):
        assert extract_currency("I paid $100") == "USD"

    def test_eur_symbol(self):
        assert extract_currency("Cost is €50") == "EUR"

    def test_gbp_symbol(self):
        assert extract_currency("£200 for services") == "GBP"

    def test_usd_keyword(self):
        assert extract_currency("I paid 100 dollars") == "USD"

    def test_egp_arabic(self):
        assert extract_currency("دفعت ٥٠٠ جنيه") == "EGP"

    def test_no_currency(self):
        assert extract_currency("I bought something") is None

    def test_sar_keyword(self):
        assert extract_currency("دفع 100 ريال") == "SAR"

    def test_aed_keyword(self):
        assert extract_currency("500 درهم") == "AED"


class TestAmountExtraction:
    def test_dollar_amount(self):
        assert extract_amount("I spent $100.50") == 100.50

    def test_dollar_no_cents(self):
        assert extract_amount("$250") == 250.0

    def test_amount_with_comma(self):
        assert extract_amount("$1,500.00") == 1500.0

    def test_arabic_amount(self):
        result = extract_amount("دفعت ٥٠٠ جنيه")
        assert result == 500.0

    def test_no_amount(self):
        assert extract_amount("no numbers here") is None

    def test_large_amount(self):
        assert extract_amount("$10,000.00") == 10000.0
