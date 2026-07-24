"""Secure Telegram pairing

Revision ID: 006
Revises: 005
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "telegram_connections",
        "telegram_chat_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_table(
        "telegram_pairings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("telegram_connections.id"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_by_chat_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "failed_attempts", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("last_failed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_telegram_pairings_secret_hash",
        "telegram_pairings",
        ["secret_hash"],
        unique=True,
    )
    op.create_index(
        "ix_telegram_pairings_connection_status",
        "telegram_pairings",
        ["connection_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_pairings_connection_status", table_name="telegram_pairings"
    )
    op.drop_index("ix_telegram_pairings_secret_hash", table_name="telegram_pairings")
    op.drop_table("telegram_pairings")
    op.execute(
        "DELETE FROM telegram_connections WHERE telegram_chat_id IS NULL"
    )
    op.alter_column(
        "telegram_connections",
        "telegram_chat_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
