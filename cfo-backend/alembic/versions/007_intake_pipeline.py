"""Secure, retry-safe intake processing metadata.

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inbox_items",
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "inbox_items",
        sa.Column(
            "duplicate_status",
            sa.String(length=20),
            nullable=False,
            server_default="unchecked",
        ),
    )
    op.add_column(
        "inbox_items",
        sa.Column("duplicate_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "inbox_items",
        sa.Column(
            "processing_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_inbox_items_company_content_hash",
        "inbox_items",
        ["company_id", "content_hash"],
    )

    op.add_column(
        "draft_transactions",
        sa.Column(
            "duplicate_status",
            sa.String(length=20),
            nullable=False,
            server_default="unchecked",
        ),
    )
    op.add_column(
        "draft_transactions",
        sa.Column("duplicate_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "draft_transactions",
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_draft_transactions_duplicate_of",
        "draft_transactions",
        "draft_transactions",
        ["duplicate_of_id"],
        ["id"],
    )
    op.create_index(
        "ix_draft_transactions_company_duplicate",
        "draft_transactions",
        ["company_id", "duplicate_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_draft_transactions_company_duplicate",
        table_name="draft_transactions",
    )
    op.drop_constraint(
        "fk_draft_transactions_duplicate_of",
        "draft_transactions",
        type_="foreignkey",
    )
    op.drop_column("draft_transactions", "duplicate_of_id")
    op.drop_column("draft_transactions", "duplicate_reason")
    op.drop_column("draft_transactions", "duplicate_status")

    op.drop_index("ix_inbox_items_company_content_hash", table_name="inbox_items")
    op.drop_column("inbox_items", "processing_attempts")
    op.drop_column("inbox_items", "duplicate_reason")
    op.drop_column("inbox_items", "duplicate_status")
    op.drop_column("inbox_items", "content_hash")
