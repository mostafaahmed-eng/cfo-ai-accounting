import re


ARABIC_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")
WESTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "ج.م": "EGP",
    "ر.س": "SAR",
    "د.إ": "AED",
    "AED": "AED",
    "SAR": "SAR",
    "EGP": "EGP",
}

CURRENCY_KEYWORDS = {
    "dollar": "USD",
    "dollars": "USD",
    "usd": "USD",
    "euro": "EUR",
    "euros": "EUR",
    "eur": "EUR",
    "pound": "GBP",
    "pounds": "GBP",
    "gbp": "GBP",
    "yen": "JPY",
    "jpy": "JPY",
    "rupee": "INR",
    "rupees": "INR",
    "inr": "INR",
    "جنيه": "EGP",
    "جنيهات": "EGP",
    "ريال": "SAR",
    "ريالات": "SAR",
    "درهم": "AED",
}


def normalize_arabic_digits(text: str) -> str:
    return text.translate(WESTERN_DIGITS)


def normalize_western_digits(text: str) -> str:
    return text


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "unknown"
    arabic_chars = sum(len(m.group()) for m in ARABIC_RANGE.finditer(text))
    total_alpha = len(re.findall(r"[a-zA-Z\u0600-\u06FF]", text))
    if total_alpha == 0:
        return "unknown"
    ratio = arabic_chars / total_alpha
    if ratio > 0.7:
        return "ar"
    if ratio < 0.3:
        return "en"
    return "mixed"


def extract_currency(text: str) -> str | None:
    text_normalized = normalize_arabic_digits(text)
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text_normalized:
            return code
    text_lower = text_normalized.lower()
    for keyword, code in CURRENCY_KEYWORDS.items():
        if keyword in text_lower:
            return code
    return None


def extract_amount(text: str) -> float | None:
    text = normalize_arabic_digits(text)
    patterns = [
        r"\$[\s]*([\d,]+\.?\d*)",
        r"([\d,]+\.?\d*)\s*(?:USD|EUR|GBP|JPY)",
        r"(?:دفعت|دفع|花了| cost|spent|paid)[\s]+([\d,]+\.?\d*)",
        r"([\d,]+\.?\d*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                return float(amount_str)
            except ValueError:
                continue
    return None
