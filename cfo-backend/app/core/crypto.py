from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class EncryptionError(RuntimeError):
    pass


def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.ENCRYPTION_KEY:
        raise EncryptionError("ENCRYPTION_KEY is not configured")
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionError(
            "Invalid encrypted value or wrong ENCRYPTION_KEY"
        ) from exc
