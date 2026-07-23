"""Make audit_logs.company_id nullable for auth-related events

Revision ID: 004
Revises: 003
Create Date: 2026-07-23
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "audit_logs",
        "company_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_logs",
        "company_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=False,
    )
