"""Add updated_at to tables missing it

Revision ID: 002
Revises: 001
Create Date: 2026-07-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    'inbox_items',
    'documents',
    'ai_extractions',
    'journal_entries',
    'journal_lines',
    'telegram_updates',
    'budgets',
    'exchange_rates',
    'notifications',
    'audit_logs',
]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, 'updated_at')
