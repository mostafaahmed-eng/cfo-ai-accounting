"""Add missing FK constraint on exchange_rates.company_id

The model has always declared a ForeignKey to companies.id, but migration 001
created the column as a bare UUID. This forward-only migration reconciles the
live schema without touching the historical migration.

Revision ID: 010
Revises: 009
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "exchange_rates_company_id_fkey"


def upgrade() -> None:
    # Orphaned rows (company_id pointing at no company) would block the FK.
    # They are unreachable application data with no owner, so remove them.
    op.execute(
        "DELETE FROM exchange_rates er "
        "WHERE NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = er.company_id)"
    )
    op.create_foreign_key(
        CONSTRAINT_NAME,
        "exchange_rates",
        "companies",
        ["company_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "exchange_rates", type_="foreignkey")
