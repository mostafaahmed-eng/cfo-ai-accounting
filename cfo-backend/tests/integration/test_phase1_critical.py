from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select


class TestJournalAccountValidation:
    pytestmark = pytest.mark.asyncio

    async def test_journal_posting_rejects_missing_category_account(
        self, db_session, client, _setup_company_and_user
    ):
        from app.models.draft_transaction import DraftTransaction

        company_id, user_id, headers = _setup_company_and_user

        draft = DraftTransaction(
            id=uuid4(),
            company_id=company_id,
            type="expense",
            amount=100,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Test expense",
            category_account_id=None,
            payment_account_id=None,
            status="ready_for_review",
        )

        from app.services.journal import JournalError, create_journal_entry_from_draft

        with pytest.raises(JournalError, match="Category account is required"):
            await create_journal_entry_from_draft(db_session, draft)

    async def test_journal_posting_rejects_missing_payment_account(
        self, db_session, client, _setup_company_and_user
    ):
        from app.models.account import Account
        from app.models.draft_transaction import DraftTransaction

        company_id, user_id, headers = _setup_company_and_user

        expense_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="5000",
            name_en="Test Expense",
            type="expense",
            subtype="general",
            is_active=True,
        )
        db_session.add(expense_account)
        await db_session.flush()

        draft = DraftTransaction(
            id=uuid4(),
            company_id=company_id,
            type="expense",
            amount=100,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Test expense",
            category_account_id=expense_account.id,
            payment_account_id=None,
            status="ready_for_review",
        )

        from app.services.journal import JournalError, create_journal_entry_from_draft

        with pytest.raises(JournalError, match="Payment account is required"):
            await create_journal_entry_from_draft(db_session, draft)

    async def test_journal_posting_rejects_foreign_account(
        self, db_session, client, _setup_company_and_user
    ):
        from app.models.account import Account
        from app.models.draft_transaction import DraftTransaction

        company_id, user_id, headers = _setup_company_and_user

        foreign_account_id = uuid4()

        category_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="5000",
            name_en="Test Expense",
            type="expense",
            subtype="general",
            is_active=True,
        )
        db_session.add(category_account)
        await db_session.flush()

        draft = DraftTransaction(
            id=uuid4(),
            company_id=company_id,
            type="expense",
            amount=100,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Test expense",
            category_account_id=category_account.id,
            payment_account_id=foreign_account_id,
            status="ready_for_review",
        )

        from app.services.journal import JournalError, create_journal_entry_from_draft

        with pytest.raises(JournalError, match="not found or not active"):
            await create_journal_entry_from_draft(db_session, draft)

    async def test_journal_posting_succeeds_with_valid_company_accounts(
        self, db_session, client, _setup_company_and_user
    ):
        from app.models.account import Account
        from app.models.draft_transaction import DraftTransaction

        company_id, user_id, headers = _setup_company_and_user

        expense_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="5000",
            name_en="Test Expense",
            type="expense",
            subtype="general",
            is_active=True,
        )
        payment_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="1000",
            name_en="Cash",
            type="asset",
            subtype="cash",
            is_active=True,
        )
        db_session.add_all([expense_account, payment_account])
        await db_session.flush()

        draft = DraftTransaction(
            id=uuid4(),
            company_id=company_id,
            type="expense",
            amount=250,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Valid expense",
            category_account_id=expense_account.id,
            payment_account_id=payment_account.id,
            status="ready_for_review",
        )
        db_session.add(draft)
        await db_session.flush()

        from app.services.journal import create_journal_entry_from_draft

        entry = await create_journal_entry_from_draft(db_session, draft)
        assert entry is not None
        assert entry.status == "posted"
        assert entry.company_id == company_id

    async def test_journal_entry_is_balanced(
        self, db_session, client, _setup_company_and_user
    ):
        from app.models.account import Account
        from app.models.draft_transaction import DraftTransaction
        from app.models.journal import JournalLine

        company_id, user_id, headers = _setup_company_and_user

        expense_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="5000",
            name_en="Test Expense",
            type="expense",
            subtype="general",
            is_active=True,
        )
        payment_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="1000",
            name_en="Cash",
            type="asset",
            subtype="cash",
            is_active=True,
        )
        db_session.add_all([expense_account, payment_account])
        await db_session.flush()

        draft = DraftTransaction(
            id=uuid4(),
            company_id=company_id,
            type="expense",
            amount=500,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Balance test",
            category_account_id=expense_account.id,
            payment_account_id=payment_account.id,
            status="ready_for_review",
        )
        db_session.add(draft)
        await db_session.flush()

        from app.services.journal import create_journal_entry_from_draft

        entry = await create_journal_entry_from_draft(db_session, draft)

        lines_result = await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
        )
        lines = lines_result.scalars().all()
        assert len(lines) == 2

        total_debit = sum(float(line.debit) for line in lines)
        total_credit = sum(float(line.credit) for line in lines)
        assert abs(total_debit - total_credit) < 0.001

    async def test_journal_accounts_belong_to_same_company(
        self, db_session, client, _setup_company_and_user
    ):
        from app.models.account import Account
        from app.models.company import Company
        from app.models.draft_transaction import DraftTransaction

        company_id, user_id, headers = _setup_company_and_user

        other_company = Company(
            id=uuid4(),
            name="Other Company",
            country_code="US",
            base_currency="USD",
            fiscal_year_start=1,
            timezone="UTC",
        )
        db_session.add(other_company)
        await db_session.flush()

        expense_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="5000",
            name_en="Test Expense",
            type="expense",
            subtype="general",
            is_active=True,
        )
        payment_account = Account(
            id=uuid4(),
            company_id=other_company.id,
            code="1000",
            name_en="Other Cash",
            type="asset",
            subtype="cash",
            is_active=True,
        )
        db_session.add_all([expense_account, payment_account])
        await db_session.flush()

        draft = DraftTransaction(
            id=uuid4(),
            company_id=company_id,
            type="expense",
            amount=100,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Cross-company test",
            category_account_id=expense_account.id,
            payment_account_id=payment_account.id,
            status="ready_for_review",
        )
        db_session.add(draft)
        await db_session.flush()

        from app.services.journal import JournalError, create_journal_entry_from_draft

        with pytest.raises(JournalError, match="not found or not active"):
            await create_journal_entry_from_draft(db_session, draft)


class TestTelegramCallbackTenantIsolation:
    pytestmark = pytest.mark.asyncio

    async def test_callback_rejects_draft_from_other_company(
        self, db_session, client, _setup_company_and_user, monkeypatch
    ):
        from app.api.v1 import telegram as telegram_api
        from app.models.company import Company
        from app.models.draft_transaction import DraftTransaction
        from app.models.telegram import TelegramConnection

        monkeypatch.setattr(
            telegram_api.answer_telegram_callback, "delay", lambda *a, **kw: None
        )
        monkeypatch.setattr(
            telegram_api.send_telegram_response, "delay", lambda *a, **kw: None
        )

        company_id, _user_id, _headers = _setup_company_and_user

        conn = TelegramConnection(
            id=uuid4(),
            company_id=company_id,
            bot_username="testbot",
            telegram_chat_id=12345,
            connected_by=_user_id,
            status="active",
        )
        db_session.add(conn)
        await db_session.flush()

        other_company = Company(
            id=uuid4(),
            name="Other Company",
            country_code="US",
            base_currency="USD",
            fiscal_year_start=1,
            timezone="UTC",
        )
        db_session.add(other_company)
        await db_session.flush()

        other_draft = DraftTransaction(
            id=uuid4(),
            company_id=other_company.id,
            type="expense",
            amount=100,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Other company draft",
            status="ready_for_review",
        )
        db_session.add(other_draft)
        await db_session.flush()

        callback_query = {
            "id": "cb_123",
            "data": f"approve:{other_draft.id}",
            "message": {
                "chat": {"id": 12345},
                "message_id": 1,
            },
        }

        from app.api.v1.telegram import _handle_callback_query

        result = await _handle_callback_query(callback_query, db_session)
        assert result["status"] == "ok"

        draft_result = await db_session.execute(
            select(DraftTransaction).where(DraftTransaction.id == other_draft.id)
        )
        draft = draft_result.scalar_one_or_none()
        assert draft.status == "ready_for_review"

    async def test_callback_rejects_unauthenticated_chat(
        self, db_session, client, _setup_company_and_user, monkeypatch
    ):
        from app.api.v1 import telegram as telegram_api

        monkeypatch.setattr(
            telegram_api.answer_telegram_callback, "delay", lambda *a, **kw: None
        )
        monkeypatch.setattr(
            telegram_api.send_telegram_response, "delay", lambda *a, **kw: None
        )

        callback_query = {
            "id": "cb_456",
            "data": "approve:some-id",
            "message": {
                "chat": {"id": 99999},
                "message_id": 1,
            },
        }

        from app.api.v1.telegram import _handle_callback_query

        result = await _handle_callback_query(callback_query, db_session)
        assert result["status"] == "no_connection"


class TestInvitationFlow:
    pytestmark = pytest.mark.asyncio

    async def test_invitation_creates_with_hashed_token(
        self, db_session, client, _setup_company_and_user
    ):
        company_id, user_id, headers = _setup_company_and_user

        from app.models.invitation import Invitation

        response = await client.post(
            f"/api/v1/companies/{company_id}/invitations",
            json={"email": "new@example.com", "role": "ACCOUNTANT"},
            headers=headers,
        )
        assert response.status_code == 200

        result = await db_session.execute(
            select(Invitation).where(Invitation.company_id == company_id)
        )
        inv = result.scalar_one_or_none()
        assert inv is not None
        assert inv.email == "new@example.com"
        assert len(inv.token_hash) == 64
        assert inv.expires_at > datetime.now(UTC).replace(tzinfo=None)

    async def test_duplicate_pending_invitation_rejected(
        self, db_session, client, _setup_company_and_user
    ):
        company_id, user_id, headers = _setup_company_and_user

        response1 = await client.post(
            f"/api/v1/companies/{company_id}/invitations",
            json={"email": "same@example.com", "role": "ACCOUNTANT"},
            headers=headers,
        )
        assert response1.status_code == 200

        response2 = await client.post(
            f"/api/v1/companies/{company_id}/invitations",
            json={"email": "same@example.com", "role": "VIEWER"},
            headers=headers,
        )
        assert response2.status_code == 409


class TestAuditLogging:
    pytestmark = pytest.mark.asyncio

    async def test_login_failure_creates_audit_log(self, db_session, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

        from app.models.audit_log import AuditLog

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "auth.login_failed")
        )
        logs = result.scalars().all()
        assert len(logs) >= 1

    async def test_login_success_creates_audit_log(
        self, db_session, client, _setup_company_and_user
    ):
        company_id, user_id, headers = _setup_company_and_user

        from app.core.security import hash_password
        from app.models.user import User

        user_result = await db_session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one()
        user.password_hash = hash_password("testpass123")
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "testpass123"},
        )
        assert response.status_code == 200

        from app.models.audit_log import AuditLog

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "auth.login_success")
        )
        logs = result.scalars().all()
        assert len(logs) >= 1

    async def test_draft_approval_creates_audit_log(
        self, db_session, client, _setup_company_and_user
    ):
        from app.models.account import Account
        from app.models.draft_transaction import DraftTransaction

        company_id, user_id, headers = _setup_company_and_user

        expense_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="5000",
            name_en="Test Expense",
            type="expense",
            subtype="general",
            is_active=True,
        )
        payment_account = Account(
            id=uuid4(),
            company_id=company_id,
            code="1000",
            name_en="Cash",
            type="asset",
            subtype="cash",
            is_active=True,
        )
        db_session.add_all([expense_account, payment_account])
        await db_session.flush()

        draft = DraftTransaction(
            id=uuid4(),
            company_id=company_id,
            type="expense",
            amount=75,
            currency="USD",
            transaction_date=datetime.now(UTC).date(),
            description="Audit test",
            category_account_id=expense_account.id,
            payment_account_id=payment_account.id,
            status="ready_for_review",
        )
        db_session.add(draft)
        await db_session.flush()

        response = await client.post(
            f"/api/v1/draft-transactions/{draft.id}/approve",
            headers=headers,
        )
        assert response.status_code == 200

        from app.models.audit_log import AuditLog

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "draft.approved",
                AuditLog.entity_id == str(draft.id),
            )
        )
        logs = result.scalars().all()
        assert len(logs) >= 1


class TestDatetimeAwareness:
    def test_utcnow_returns_naive_utc(self):
        from app.models.base import _utcnow

        dt = _utcnow()
        assert dt.tzinfo is None
        assert dt.year >= 2024

    def test_auth_token_uses_utc(self):
        from app.services.auth import create_access_token

        token = create_access_token(str(uuid4()))
        assert isinstance(token, str)
        assert len(token) > 20
