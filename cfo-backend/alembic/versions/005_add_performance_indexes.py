"""Add performance indexes for common query patterns

Revision ID: 005
Revises: 004
Create Date: 2026-07-23
"""

from typing import Sequence, Union
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_draft_transactions_company_status",
        "draft_transactions",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_draft_transactions_company_created",
        "draft_transactions",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_inbox_items_company_status",
        "inbox_items",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_inbox_items_company_created",
        "inbox_items",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_journal_entries_company_date",
        "journal_entries",
        ["company_id", "entry_date"],
    )
    op.create_index(
        "ix_journal_entries_company_status",
        "journal_entries",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_journal_lines_account",
        "journal_lines",
        ["account_id"],
    )
    op.create_index(
        "ix_audit_logs_company_created",
        "audit_logs",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_action",
        "audit_logs",
        ["action"],
    )
    op.create_index(
        "ix_company_members_user_status",
        "company_members",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_notifications_company_user",
        "notifications",
        ["company_id", "user_id"],
    )
    op.create_index(
        "ix_vendors_company_active",
        "vendors",
        ["company_id", "is_active"],
    )
    op.create_index(
        "ix_vendors_normalized_name",
        "vendors",
        ["normalized_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_vendors_normalized_name", "vendors")
    op.drop_index("ix_vendors_company_active", "vendors")
    op.drop_index("ix_notifications_company_user", "notifications")
    op.drop_index("ix_company_members_user_status", "company_members")
    op.drop_index("ix_audit_logs_action", "audit_logs")
    op.drop_index("ix_audit_logs_company_created", "audit_logs")
    op.drop_index("ix_journal_lines_account", "journal_lines")
    op.drop_index("ix_journal_entries_company_status", "journal_entries")
    op.drop_index("ix_journal_entries_company_date", "journal_entries")
    op.drop_index("ix_inbox_items_company_created", "inbox_items")
    op.drop_index("ix_inbox_items_company_status", "inbox_items")
    op.drop_index("ix_draft_transactions_company_created", "draft_transactions")
    op.drop_index("ix_draft_transactions_company_status", "draft_transactions")
