import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "create_admin.py"


@pytest.fixture(scope="module")
def admin_script():
    spec = importlib.util.spec_from_file_location("create_admin", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestNormalizeEmail:
    def test_normalizes_case_and_whitespace(self, admin_script):
        assert (
            admin_script.normalize_email("  Admin@Example.COM  ") == "admin@example.com"
        )

    def test_valid_email_passes(self, admin_script):
        assert admin_script.normalize_email("user@domain.com") == "user@domain.com"

    def test_missing_at_sign_rejected(self, admin_script):
        with pytest.raises(ValueError):
            admin_script.normalize_email("not-an-email")

    def test_missing_domain_dot_rejected(self, admin_script):
        with pytest.raises(ValueError):
            admin_script.normalize_email("user@domain")

    def test_empty_rejected(self, admin_script):
        with pytest.raises(ValueError):
            admin_script.normalize_email("  ")


class TestValidatePasswordStrength:
    def test_too_short_rejected(self, admin_script):
        with pytest.raises(ValueError, match="at least"):
            admin_script.validate_password_strength("Ab1")

    def test_missing_uppercase_rejected(self, admin_script):
        with pytest.raises(ValueError, match="uppercase"):
            admin_script.validate_password_strength("alllower1")

    def test_missing_lowercase_rejected(self, admin_script):
        with pytest.raises(ValueError, match="lowercase"):
            admin_script.validate_password_strength("ALLUPPER1")

    def test_missing_digit_rejected(self, admin_script):
        with pytest.raises(ValueError, match="digit"):
            admin_script.validate_password_strength("NoDigitsHere")

    def test_strong_password_accepted(self, admin_script):
        assert admin_script.validate_password_strength("Str0ngPassw0rd!") is None
