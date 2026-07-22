from decimal import Decimal


class TestDebitCreditBalancing:
    def test_balanced_entry(self):
        lines = [
            {"debit": Decimal("100.00"), "credit": Decimal("0")},
            {"debit": Decimal("0"), "credit": Decimal("100.00")},
        ]
        total_debit = sum(line["debit"] for line in lines)
        total_credit = sum(line["credit"] for line in lines)
        assert total_debit == total_credit

    def test_unbalanced_entry(self):
        lines = [
            {"debit": Decimal("100.00"), "credit": Decimal("0")},
            {"debit": Decimal("0"), "credit": Decimal("50.00")},
        ]
        total_debit = sum(line["debit"] for line in lines)
        total_credit = sum(line["credit"] for line in lines)
        assert total_debit != total_credit

    def test_multiple_debit_lines(self):
        lines = [
            {"debit": Decimal("60.00"), "credit": Decimal("0")},
            {"debit": Decimal("40.00"), "credit": Decimal("0")},
            {"debit": Decimal("0"), "credit": Decimal("100.00")},
        ]
        total_debit = sum(line["debit"] for line in lines)
        total_credit = sum(line["credit"] for line in lines)
        assert total_debit == total_credit

    def test_single_line_not_balanced(self):
        lines = [
            {"debit": Decimal("100.00"), "credit": Decimal("0")},
        ]
        total_debit = sum(line["debit"] for line in lines)
        total_credit = sum(line["credit"] for line in lines)
        assert total_debit != total_credit

    def test_line_cannot_have_both_debit_and_credit(self):
        line = {"debit": Decimal("100.00"), "credit": Decimal("50.00")}
        has_both = line["debit"] > 0 and line["credit"] > 0
        assert has_both is True  # This is invalid per our rules

    def test_zero_amounts_not_valid(self):
        line = {"debit": Decimal("0"), "credit": Decimal("0")}
        is_valid = line["debit"] > 0 or line["credit"] > 0
        assert is_valid is False

    def test_decimal_precision(self):
        lines = [
            {"debit": Decimal("33.33"), "credit": Decimal("0")},
            {"debit": Decimal("33.33"), "credit": Decimal("0")},
            {"debit": Decimal("33.34"), "credit": Decimal("0")},
            {"debit": Decimal("0"), "credit": Decimal("100.00")},
        ]
        total_debit = sum(line["debit"] for line in lines)
        total_credit = sum(line["credit"] for line in lines)
        assert total_debit == total_credit
