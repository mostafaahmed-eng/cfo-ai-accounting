import pytest
from cryptography.fernet import Fernet

import app.core.crypto as crypto_module
from app.core.crypto import EncryptionError, decrypt_secret, encrypt_secret

DETERMINISTIC_KEY = Fernet.generate_key()


@pytest.fixture()
def _stub_fernet(monkeypatch):
    fernet = Fernet(DETERMINISTIC_KEY)
    monkeypatch.setattr(crypto_module, "_fernet", lambda: fernet)


def test_roundtrip(_stub_fernet):
    value = "super-secret-telegram-token"
    encrypted = encrypt_secret(value)
    assert encrypted != value
    assert decrypt_secret(encrypted) == value


def test_decrypt_with_wrong_key(_stub_fernet):
    encrypted = encrypt_secret("secret")
    wrong = Fernet(Fernet.generate_key())
    monkeypatch_holder = crypto_module._fernet
    crypto_module._fernet = lambda: wrong
    try:
        with pytest.raises(EncryptionError):
            decrypt_secret(encrypted)
    finally:
        crypto_module._fernet = monkeypatch_holder


def test_encrypt_without_key():
    original = crypto_module._fernet
    crypto_module._fernet = lambda: (_ for _ in ()).throw(
        EncryptionError("ENCRYPTION_KEY is not configured")
    )
    try:
        with pytest.raises(EncryptionError):
            encrypt_secret("x")
    finally:
        crypto_module._fernet = original
