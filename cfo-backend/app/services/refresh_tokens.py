from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth import create_refresh_token, token_fingerprint

settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def issue_refresh_token(
    db: AsyncSession,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Create a refresh token, store its fingerprint, and return the token."""
    jti = uuid4()
    token = create_refresh_token(str(user.id), ver=user.token_version, jti=str(jti))
    db.add(
        RefreshToken(
            id=jti,
            user_id=user.id,
            token_hash=token_fingerprint(token),
            expires_at=_utcnow()
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    await db.flush()
    return token


async def revoke_all_user_tokens(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )
    await db.flush()


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    token: str,
    jti: str,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str | None:
    """Atomically rotate a refresh token.

    The UPDATE ... RETURNING is the concurrency guard: only one request can
    match an un-revoked row, so a second simultaneous refresh with the same
    token (a rotation race or replay) matches zero rows. Any replay/rotation
    collision revokes the whole token family for the user, and None is
    returned so the caller can force a clean re-authentication.
    """
    new_jti = uuid4()
    now = _utcnow()
    new_token = create_refresh_token(
        str(user.id), ver=user.token_version, jti=str(new_jti)
    )
    # Insert the successor row first so the replaced_by_id FK reference from
    # the old row is valid when the atomic UPDATE below runs.
    db.add(
        RefreshToken(
            id=new_jti,
            user_id=user.id,
            token_hash=token_fingerprint(new_token),
            expires_at=now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    await db.flush()

    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.id == jti,
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now, replaced_by_id=new_jti)
        .returning(RefreshToken.id)
    )
    if result.scalar_one_or_none() is None:
        # Rotation race or replay: revoke the whole family (which also retires
        # the successor row just inserted) and signal a clean re-authentication.
        await revoke_all_user_tokens(db, user.id)
        return None

    return new_token
