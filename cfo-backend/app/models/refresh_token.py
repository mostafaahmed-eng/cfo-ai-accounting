from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel, TimestampMixin


class RefreshToken(BaseModel, TimestampMixin):
    __tablename__ = "refresh_tokens"

    # The token's `jti` claim equals the row id. Rows are keyed by that id and
    # chained via replaced_by_id on every rotation so reuse is detectable.
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # SHA-256 hex digest of the raw refresh token. The plaintext token is never
    # stored server-side.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_id = Column(
        UUID(as_uuid=True), ForeignKey("refresh_tokens.id"), nullable=True
    )
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    __table_args__ = (Index("ix_refresh_tokens_user_active", "user_id", "revoked_at"),)
