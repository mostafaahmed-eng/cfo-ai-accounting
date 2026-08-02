import pytest
from cryptography.fernet import Fernet

from app.config import Settings


def test_production_requires_encryption_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    monkeypatch.setenv("SECRET_KEY", "a-really-long-random-production-secret-key")
    with pytest.raises(ValueError, match="ENCRYPTION_KEY must be set in production"):
        Settings()


def test_production_rejects_invalid_fernet_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key")
    monkeypatch.setenv("SECRET_KEY", "a-really-long-random-production-secret-key")
    with pytest.raises(ValueError, match="valid Fernet key"):
        Settings()


def test_production_accepts_valid_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("SECRET_KEY", "a-really-long-random-production-secret-key")
    assert Settings().ENCRYPTION_KEY


def test_development_accepts_placeholder(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    assert Settings().ENCRYPTION_KEY == ""
