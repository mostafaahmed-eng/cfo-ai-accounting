import pytest
from pydantic import ValidationError
from app.schemas.ai_extraction import ExtractionResult


class TestAIOutputValidation:
    def test_valid_extraction(self):
        data = {
            "document_type": "receipt",
            "transaction_type": "expense",
            "amount": 100.0,
            "tax_amount": 0,
            "currency": "USD",
            "transaction_date": "2026-07-18",
            "vendor": {"name": "Example Hosting", "tax_number": None},
            "description": "VPS hosting",
            "category_hint": "Hosting",
            "payment_method_hint": "card",
            "reference_number": None,
            "language": "en",
            "confidence": {
                "overall": 0.91,
                "amount": 0.99,
                "currency": 0.98,
                "date": 0.72,
                "category": 0.88,
            },
            "needs_clarification": True,
            "questions": ["Which card or bank account was used?"],
        }
        result = ExtractionResult(**data)
        assert result.amount == 100.0
        assert result.currency == "USD"
        assert result.vendor.name == "Example Hosting"
        assert result.confidence.overall == 0.91
        assert len(result.questions) == 1

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            ExtractionResult(amount=100)

    def test_invalid_document_type(self):
        data = {
            "document_type": "invalid_type",
            "transaction_type": "expense",
            "amount": 50.0,
            "tax_amount": 0,
            "currency": "USD",
            "transaction_date": "2026-07-18",
            "vendor": {"name": "Test"},
            "description": "Test",
            "category_hint": "Test",
            "language": "en",
            "confidence": {
                "overall": 0.9,
                "amount": 0.9,
                "currency": 0.9,
                "date": 0.9,
                "category": 0.9,
            },
        }
        # This should still work as document_type is just a string
        result = ExtractionResult(**data)
        assert result.document_type == "invalid_type"

    def test_zero_amount(self):
        data = {
            "document_type": "text_transaction",
            "transaction_type": "expense",
            "amount": 0.0,
            "tax_amount": 0,
            "currency": "USD",
            "transaction_date": "2026-07-18",
            "vendor": {"name": "Test"},
            "description": "Test",
            "category_hint": "Test",
            "language": "en",
            "confidence": {
                "overall": 0.5,
                "amount": 0.5,
                "currency": 0.5,
                "date": 0.5,
                "category": 0.5,
            },
        }
        result = ExtractionResult(**data)
        assert result.amount == 0.0

    def test_confidence_scores(self):
        data = {
            "document_type": "receipt",
            "transaction_type": "expense",
            "amount": 100.0,
            "tax_amount": 15.0,
            "currency": "USD",
            "transaction_date": "2026-07-18",
            "vendor": {"name": "Test"},
            "description": "Test",
            "category_hint": "Test",
            "language": "en",
            "confidence": {
                "overall": 0.95,
                "amount": 1.0,
                "currency": 1.0,
                "date": 0.8,
                "category": 0.9,
            },
        }
        result = ExtractionResult(**data)
        assert result.confidence.overall == 0.95
        assert result.confidence.amount == 1.0
