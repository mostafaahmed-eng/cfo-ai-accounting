import json
import time

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.ai_extraction import ExtractionResult

settings = get_settings()

EXTRACTION_PROMPT_VERSION = "v1.0"
SYSTEM_PROMPT = """You are a financial data extraction AI. Extract structured data from receipts, invoices, or expense text.
Return valid JSON matching this schema:
{
    "document_type": "receipt | invoice | text_transaction | unknown",
    "transaction_type": "expense | income | transfer | unknown",
    "amount": number,
    "tax_amount": number,
    "currency": "USD",
    "transaction_date": "YYYY-MM-DD",
    "vendor": {"name": "string", "tax_number": null},
    "description": "string",
    "category_hint": "string",
    "payment_method_hint": "string | null",
    "reference_number": "string | null",
    "language": "en | ar",
    "confidence": {"overall": 0.0, "amount": 0.0, "currency": 0.0, "date": 0.0, "category": 0.0},
    "needs_clarification": boolean,
    "questions": ["string"]
}"""


async def extract_from_text(text: str, language: str = "en") -> dict:
    start = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Language: {language}\n\nExtract financial data from this:\n{text}",
                    },
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        )
        response.raise_for_status()
        result = response.json()

    elapsed_ms = int((time.time() - start) * 1000)
    content = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    import re

    cleaned = content.strip()
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if md_match:
        cleaned = md_match.group(1).strip()

    try:
        extracted = json.loads(cleaned)
    except json.JSONDecodeError:
        extracted = {}

    validated = None
    validation_error = None
    try:
        validated = ExtractionResult.model_validate(extracted)
    except ValidationError as e:
        validation_error = str(e)

    estimated_cost = _estimate_cost(
        settings.OPENROUTER_MODEL, input_tokens, output_tokens
    )

    return {
        "extracted": validated.model_dump(mode="json") if validated else extracted,
        "validated": validated is not None,
        "validation_error": validation_error,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": estimated_cost,
        "processing_ms": elapsed_ms,
    }


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = {
        "google/gemini-2.5-flash": (1.50 / 1_000_000, 7.50 / 1_000_000),
        "google/gemini-2.0-flash-001": (0.10 / 1_000_000, 0.40 / 1_000_000),
    }
    if model in costs:
        input_rate, output_rate = costs[model]
        return round(input_tokens * input_rate + output_tokens * output_rate, 6)
    return 0.0
