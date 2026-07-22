"""Initial schema - all tables

Revision ID: 001
Revises: 
Create Date: 2026-07-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_status_enum = postgresql.ENUM('active', 'invited', 'disabled', name='userstatus', create_type=False)
    language_enum = postgresql.ENUM('en', 'ar', name='language', create_type=False)

    user_status_enum.create(op.get_bind(), checkfirst=True)
    language_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('language', language_enum, nullable=False, server_default='en'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'),
        sa.Column('status', user_status_enum, nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('legal_name', sa.String(255), nullable=True),
        sa.Column('country_code', sa.String(2), nullable=False),
        sa.Column('base_currency', sa.String(3), nullable=False),
        sa.Column('fiscal_year_start', sa.SmallInteger, nullable=False, server_default='1'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'),
        sa.Column('tax_number', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'company_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('joined_at', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'user_id'),
    )

    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('name_en', sa.String(255), nullable=False),
        sa.Column('name_ar', sa.String(255), nullable=True),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('subtype', sa.String(50), nullable=False),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('parent_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('is_payment_account', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_system', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'code'),
    )

    op.create_table(
        'inbox_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('source_reference', sa.String(255), nullable=True),
        sa.Column('content_type', sa.String(20), nullable=False),
        sa.Column('original_text', sa.Text, nullable=True),
        sa.Column('detected_language', sa.String(10), nullable=False, server_default='unknown'),
        sa.Column('status', sa.String(20), nullable=False, server_default='received'),
        sa.Column('submitted_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.UniqueConstraint('company_id', 'source', 'idempotency_key'),
    )

    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('inbox_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inbox_items.id'), nullable=True),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('original_name', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger, nullable=False),
        sa.Column('sha256_hash', sa.String(64), nullable=False),
        sa.Column('document_type', sa.String(20), nullable=False, server_default='other'),
        sa.Column('upload_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'ai_extractions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('inbox_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inbox_items.id'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('prompt_version', sa.String(50), nullable=False),
        sa.Column('request_payload', postgresql.JSONB, nullable=False),
        sa.Column('raw_response', postgresql.JSONB, nullable=False),
        sa.Column('validated_result', postgresql.JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('input_tokens', sa.Integer, nullable=True),
        sa.Column('output_tokens', sa.Integer, nullable=True),
        sa.Column('estimated_cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('processing_ms', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'vendors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('normalized_name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('tax_number', sa.String(100), nullable=True),
        sa.Column('country_code', sa.String(2), nullable=True),
        sa.Column('default_expense_account', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('default_currency', sa.String(3), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'vendor_aliases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id'), nullable=False),
        sa.Column('alias', sa.String(255), nullable=False),
        sa.Column('normalized_alias', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('vendor_id', 'normalized_alias'),
    )

    op.create_table(
        'draft_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('inbox_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inbox_items.id'), nullable=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(18, 4), nullable=False),
        sa.Column('tax_amount', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('transaction_date', sa.Date, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id'), nullable=True),
        sa.Column('category_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('payment_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('reference_number', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('ai_confidence', sa.Numeric(5, 4), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'approval_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('entity_id', sa.String, nullable=False),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('comment', sa.Text, nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'journal_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('entry_number', sa.String(50), nullable=False),
        sa.Column('entry_date', sa.Date, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('source_id', sa.String, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('exchange_rate', sa.Numeric(18, 8), nullable=False, server_default='1'),
        sa.Column('posted_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('posted_at', sa.DateTime, nullable=True),
        sa.Column('reversed_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('journal_entries.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'entry_number'),
    )

    op.create_table(
        'journal_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('journal_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('journal_entries.id'), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('debit', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('credit', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('base_debit', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('base_credit', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('debit >= 0', name='ck_debit_non_negative'),
        sa.CheckConstraint('credit >= 0', name='ck_credit_non_negative'),
        sa.CheckConstraint(
            "(debit = 0 AND credit > 0) OR (debit > 0 AND credit = 0)",
            name='ck_debit_xor_credit',
        ),
    )

    op.create_table(
        'telegram_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('bot_username', sa.String(100), nullable=False),
        sa.Column('telegram_chat_id', sa.BigInteger, nullable=False),
        sa.Column('connected_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('telegram_chat_id'),
    )

    op.create_table(
        'telegram_updates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('telegram_connections.id'), nullable=False),
        sa.Column('telegram_update_id', sa.BigInteger, nullable=False),
        sa.Column('message_id', sa.BigInteger, nullable=True),
        sa.Column('chat_id', sa.BigInteger, nullable=False),
        sa.Column('update_type', sa.String(50), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('processing_status', sa.String(20), nullable=False, server_default='received'),
        sa.Column('inbox_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inbox_items.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('telegram_update_id'),
    )

    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('start_date', sa.String(10), nullable=False),
        sa.Column('end_date', sa.String(10), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'budget_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('budget_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('budgets.id'), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=False),
        sa.Column('planned_amount', sa.Numeric(18, 4), nullable=False),
        sa.Column('alert_percentage', sa.Numeric(5, 2), nullable=False, server_default='80'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('budget_id', 'account_id'),
    )

    op.create_table(
        'exchange_rates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('base_currency', sa.String(3), nullable=False),
        sa.Column('quote_currency', sa.String(3), nullable=False),
        sa.Column('rate', sa.Numeric(18, 8), nullable=False),
        sa.Column('rate_date', sa.Date, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'base_currency', 'quote_currency', 'rate_date'),
    )

    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.String, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('sent_at', sa.DateTime, nullable=True),
        sa.Column('read_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String, nullable=False),
        sa.Column('before_data', postgresql.JSONB, nullable=True),
        sa.Column('after_data', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('notifications')
    op.drop_table('exchange_rates')
    op.drop_table('budget_lines')
    op.drop_table('budgets')
    op.drop_table('telegram_updates')
    op.drop_table('telegram_connections')
    op.drop_table('journal_lines')
    op.drop_table('journal_entries')
    op.drop_table('approval_requests')
    op.drop_table('draft_transactions')
    op.drop_table('vendor_aliases')
    op.drop_table('vendors')
    op.drop_table('ai_extractions')
    op.drop_table('documents')
    op.drop_table('inbox_items')
    op.drop_table('accounts')
    op.drop_table('company_members')
    op.drop_table('companies')
    op.drop_table('users')

    postgresql.ENUM(name='language').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='userstatus').drop(op.get_bind(), checkfirst=True)
