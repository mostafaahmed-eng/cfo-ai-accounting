import hashlib
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

settings = get_settings()


def create_access_token(
    user_id: str, ver: int = 0, expires_delta: timedelta | None = None
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {"sub": user_id, "type": "access", "ver": ver, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: str, ver: int = 0, jti: str | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    claims: dict = {"sub": user_id, "type": "refresh", "ver": ver, "exp": expire}
    if jti:
        claims["jti"] = jti
    return jwt.encode(
        claims,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def token_fingerprint(token: str) -> str:
    """SHA-256 hex digest used as the server-side record of a refresh token.

    The plaintext token is never persisted; only this digest is stored.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
