from uuid import uuid4

from app.dependencies import is_platform_admin
from app.models.user import User


def _user(email):
    return User(
        id=uuid4(),
        email=email,
        name="Platform Test",
        language="en",
        timezone="UTC",
        status="active",
    )


class _FakeSettings:
    def __init__(self, emails):
        self.PLATFORM_ADMIN_EMAILS = emails


def test_platform_admin_emails_are_trimmed_and_case_normalized(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.get_settings",
        lambda: _FakeSettings("  Admin@Example.COM ,   Owner@Acme.io  "),
    )

    # Configured values match regardless of whitespace or casing.
    assert is_platform_admin(_user("admin@example.com"))
    assert is_platform_admin(_user("OWNER@acme.io"))
    # The user's own email is normalized identically on the lookup side.
    assert is_platform_admin(_user("  ADMIN@EXAMPLE.COM  "))
    assert not is_platform_admin(_user("intruder@example.com"))
    assert not is_platform_admin(_user("admin@example.com.evil.io"))


def test_platform_admin_empty_config_denies_everyone(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.get_settings",
        lambda: _FakeSettings(""),
    )
    assert not is_platform_admin(_user("admin@example.com"))


def test_platform_admin_single_email_without_list_quirks(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.get_settings",
        lambda: _FakeSettings("admin@example.com"),
    )
    assert is_platform_admin(_user("admin@example.com"))
    assert not is_platform_admin(_user("admin@example.com,owner@acme.io"))
