import io
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select

from app.api.v1 import telegram as telegram_api
from app.enums import UserStatus
from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyMember
from app.models.document import Document
from app.models.inbox_item import InboxItem
from app.models.telegram import TelegramConnection, TelegramPairing, TelegramUpdate
from app.models.user import User
from app.services.telegram_pairing import create_pairing

FAKE_WEBHOOK_SECRET = "fake-test-webhook-secret"


@pytest.fixture(autouse=True)
def _fake_telegram(monkeypatch):
    monkeypatch.setattr(telegram_api.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(
        telegram_api.settings, "TELEGRAM_WEBHOOK_SECRET", FAKE_WEBHOOK_SECRET
    )
    monkeypatch.setattr(
        telegram_api.settings, "TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK", False
    )
    monkeypatch.setattr(telegram_api.settings, "TELEGRAM_BOT_USERNAME", "testbot")
    monkeypatch.setattr(
        telegram_api.send_telegram_response, "delay", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        telegram_api.send_telegram_edit, "delay", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        telegram_api.answer_telegram_callback, "delay", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        telegram_api.run_ai_extraction, "delay", lambda *args, **kwargs: None
    )


def _webhook_headers(secret=FAKE_WEBHOOK_SECRET):
    return {"X-Telegram-Bot-Api-Secret-Token": secret}


def _start_update(update_id: int, chat_id: int, code: str | None):
    text = "/start" if code is None else f"/start {code}"
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "chat": {"id": chat_id},
            "text": text,
        },
    }


def _jpeg() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), color="white").save(output, format="JPEG")
    return output.getvalue()


async def _request_pairing(client, db_session, company_id, headers):
    membership_result = await db_session.execute(
        select(CompanyMember).where(CompanyMember.company_id == company_id)
    )
    membership = membership_result.scalar_one()
    user_result = await db_session.execute(
        select(User).where(User.id == membership.user_id)
    )
    user_result.scalar_one().status = UserStatus.active
    await db_session.flush()

    response = await client.post(
        "/api/v1/integrations/telegram/connect", headers=headers
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is False
    assert payload["status"] == "pending"
    assert payload["pairing_code"]
    assert payload["chat_id"] is None
    return payload


@pytest.mark.asyncio
async def test_connect_pairing_link_uses_configured_username_without_duplication(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    payload = await _request_pairing(client, db_session, company_id, headers)

    assert payload["bot_username"] == "testbot"
    assert payload["pairing_link"] == (
        f"https://t.me/testbot?start={payload['pairing_code']}"
    )
    assert payload["pairing_link"].count("testbot") == 1


@pytest.mark.asyncio
async def test_connect_refreshes_stale_db_bot_username(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, headers = _setup_company_and_user
    stale = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="stalebotstalebot",
        telegram_chat_id=None,
        connected_by=user_id,
        status="pending_chat_id",
    )
    db_session.add(stale)
    await db_session.flush()

    payload = await _request_pairing(client, db_session, company_id, headers)

    assert payload["bot_username"] == "testbot"
    assert payload["pairing_link"] == (
        f"https://t.me/testbot?start={payload['pairing_code']}"
    )
    assert payload["pairing_link"].count("testbot") == 1

    result = await db_session.execute(
        select(TelegramConnection).where(TelegramConnection.company_id == company_id)
    )
    stored = result.scalar_one()
    assert stored.bot_username == "testbot"


@pytest.mark.asyncio
async def test_connect_fails_clearly_when_username_not_configured(
    client, db_session, _setup_company_and_user, monkeypatch
):
    company_id, _, headers = _setup_company_and_user
    membership_result = await db_session.execute(
        select(CompanyMember).where(CompanyMember.company_id == company_id)
    )
    membership = membership_result.scalar_one()
    user_result = await db_session.execute(
        select(User).where(User.id == membership.user_id)
    )
    user_result.scalar_one().status = UserStatus.active
    await db_session.flush()

    monkeypatch.setattr(telegram_api.settings, "TELEGRAM_BOT_USERNAME", "")
    response = await client.post(
        "/api/v1/integrations/telegram/connect", headers=headers
    )
    assert response.status_code == 503
    assert "TELEGRAM_BOT_USERNAME" in response.json()["detail"]


@pytest.mark.asyncio
async def test_successful_pairing_records_numeric_chat_id(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    pairing = await _request_pairing(client, db_session, company_id, headers)

    response = await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20001, 987654321, pairing["pairing_code"]),
        headers=_webhook_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"status": "connected"}

    result = await db_session.execute(
        select(TelegramConnection).where(TelegramConnection.company_id == company_id)
    )
    connection = result.scalar_one()
    assert connection.status == "active"
    assert connection.telegram_chat_id == 987654321
    assert isinstance(connection.telegram_chat_id, int)

    pairing_result = await db_session.execute(
        select(TelegramPairing).where(TelegramPairing.connection_id == connection.id)
    )
    pairing_row = pairing_result.scalar_one()
    assert pairing_row.status == "consumed"
    assert pairing_row.consumed_by_chat_id == 987654321
    assert pairing_row.consumed_at is not None
    assert pairing_row.secret_hash != pairing["pairing_code"]
    assert len(pairing_row.secret_hash) == 64

    update_result = await db_session.execute(
        select(TelegramUpdate).where(TelegramUpdate.telegram_update_id == 20001)
    )
    stored_update = update_result.scalar_one()
    assert stored_update.payload["message"]["text"] == "/start [REDACTED]"


@pytest.mark.asyncio
async def test_telegram_photo_uses_shared_document_intake(
    client, db_session, _setup_company_and_user, monkeypatch
):
    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=987654324,
        connected_by=user_id,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()

    uploaded = []
    dispatched = []
    responses = []

    async def fake_download(file_id, token=None):
        assert file_id == "largest-photo"
        return _jpeg()

    async def fake_upload(key, content, mime_type):
        uploaded.append((key, content, mime_type))

    monkeypatch.setattr(telegram_api.telegram_client, "download_file", fake_download)
    monkeypatch.setattr(
        "app.services.document_intake.storage_client.upload_file", fake_upload
    )
    monkeypatch.setattr(
        telegram_api.process_receipt,
        "delay",
        lambda inbox_id, document_id: dispatched.append((inbox_id, document_id)),
    )
    monkeypatch.setattr(
        telegram_api.send_telegram_response,
        "delay",
        lambda *args: responses.append(args),
    )

    response = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 20015,
            "message": {
                "message_id": 20015,
                "chat": {"id": 987654324},
                "photo": [
                    {
                        "file_id": "small-photo",
                        "file_unique_id": "small",
                        "file_size": 100,
                    },
                    {
                        "file_id": "largest-photo",
                        "file_unique_id": "largest",
                        "file_size": len(_jpeg()),
                    },
                ],
            },
        },
        headers=_webhook_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    document = (
        (
            await db_session.execute(
                select(Document).where(Document.company_id == company_id)
            )
        )
        .scalars()
        .one()
    )
    item = (
        await db_session.execute(
            select(InboxItem).where(InboxItem.id == document.inbox_item_id)
        )
    ).scalar_one()
    update = (
        await db_session.execute(
            select(TelegramUpdate).where(TelegramUpdate.telegram_update_id == 20015)
        )
    ).scalar_one()
    assert document.mime_type == "image/jpeg"
    assert document.upload_status == "stored"
    assert document.size_bytes == len(_jpeg())
    assert item.source == "telegram"
    assert item.content_type == "image"
    assert item.status == "queued"
    assert update.inbox_item_id == item.id
    assert uploaded[0][2] == "image/jpeg"
    assert dispatched == [(str(item.id), str(document.id))]
    assert "Processing your receipt" in responses[-1][1]


@pytest.mark.asyncio
async def test_telegram_unsupported_content_gets_clear_response(
    client, db_session, _setup_company_and_user, monkeypatch
):
    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=987654325,
        connected_by=user_id,
        status="active",
    )
    db_session.add(connection)
    await db_session.flush()
    responses = []
    monkeypatch.setattr(
        telegram_api.send_telegram_response,
        "delay",
        lambda *args: responses.append(args),
    )

    response = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 20016,
            "message": {
                "message_id": 20016,
                "chat": {"id": 987654325},
                "voice": {"file_id": "voice-file"},
            },
        },
        headers=_webhook_headers(),
    )

    assert response.status_code == 200
    update = (
        await db_session.execute(
            select(TelegramUpdate).where(TelegramUpdate.telegram_update_id == 20016)
        )
    ).scalar_one()
    assert update.processing_status == "unsupported_content"
    assert "can't process that voice" in responses[-1][1]


@pytest.mark.asyncio
async def test_disconnect_reconnect_pairing_is_repeatable(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    connection_id = None
    chat_id = 987654322

    for cycle, update_id in enumerate((20011, 20012), start=1):
        pairing = await _request_pairing(client, db_session, company_id, headers)
        response = await client.post(
            "/api/v1/telegram/webhook",
            json=_start_update(update_id, chat_id, pairing["pairing_code"]),
            headers=_webhook_headers(),
        )
        assert response.status_code == 200
        assert response.json() == {"status": "connected"}

        result = await db_session.execute(
            select(TelegramConnection).where(
                TelegramConnection.company_id == company_id
            )
        )
        connection = result.scalar_one()
        if cycle == 1:
            connection_id = connection.id
        else:
            assert connection.id == connection_id
        assert connection.status == "active"
        assert connection.telegram_chat_id == chat_id

        disconnected = await client.delete(
            "/api/v1/integrations/telegram/disconnect", headers=headers
        )
        assert disconnected.status_code == 200
        assert connection.status == "disabled"
        assert connection.telegram_chat_id is None


@pytest.mark.asyncio
async def test_reconnect_clears_legacy_disabled_chat_binding(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, headers = _setup_company_and_user
    chat_id = 987654323
    legacy = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="test_bot",
        telegram_chat_id=chat_id,
        connected_by=user_id,
        status="disabled",
    )
    pending = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="test_bot",
        telegram_chat_id=None,
        connected_by=user_id,
        status="pending_chat_id",
    )
    db_session.add_all([legacy, pending])
    await db_session.flush()

    pairing = await _request_pairing(client, db_session, company_id, headers)
    assert legacy.telegram_chat_id is None

    response = await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20013, chat_id, pairing["pairing_code"]),
        headers=_webhook_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"status": "connected"}
    assert pending.status == "active"
    assert pending.telegram_chat_id == chat_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "update_id"),
    [
        (None, 20002),
        ("bad code!", 20003),
        ("A" * 43, 20004),
    ],
)
async def test_missing_malformed_and_unknown_pairing_codes_do_not_connect(
    client, db_session, _setup_company_and_user, code, update_id
):
    company_id, _, headers = _setup_company_and_user
    await _request_pairing(client, db_session, company_id, headers)

    response = await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(update_id, 111000 + update_id, code),
        headers=_webhook_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"status": "pairing_failed"}

    connection_result = await db_session.execute(
        select(TelegramConnection).where(TelegramConnection.company_id == company_id)
    )
    connection = connection_result.scalar_one()
    assert connection.status == "pending_chat_id"
    assert connection.telegram_chat_id is None


@pytest.mark.asyncio
async def test_expired_pairing_code_is_rejected(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    pairing = await _request_pairing(client, db_session, company_id, headers)
    result = await db_session.execute(
        select(TelegramPairing).where(TelegramPairing.company_id == company_id)
    )
    pairing_row = result.scalar_one()
    pairing_row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        seconds=1
    )
    await db_session.flush()

    response = await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20005, 555001, pairing["pairing_code"]),
        headers=_webhook_headers(),
    )
    assert response.json() == {"status": "pairing_failed"}
    assert pairing_row.status == "expired"


@pytest.mark.asyncio
async def test_pairing_code_is_single_use_across_two_chats(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    pairing = await _request_pairing(client, db_session, company_id, headers)

    first = await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20006, 600001, pairing["pairing_code"]),
        headers=_webhook_headers(),
    )
    second = await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20007, 600002, pairing["pairing_code"]),
        headers=_webhook_headers(),
    )
    assert first.json() == {"status": "connected"}
    assert second.json() == {"status": "pairing_failed"}

    result = await db_session.execute(
        select(TelegramConnection).where(TelegramConnection.company_id == company_id)
    )
    connection = result.scalar_one()
    assert connection.telegram_chat_id == 600001

    pairing_result = await db_session.execute(
        select(TelegramPairing).where(TelegramPairing.connection_id == connection.id)
    )
    pairing_row = pairing_result.scalar_one()
    assert pairing_row.status == "consumed"
    assert pairing_row.consumed_by_chat_id == 600001
    assert pairing_row.failed_attempts == 1


@pytest.mark.asyncio
async def test_stranger_message_cannot_claim_pending_company(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    await _request_pairing(client, db_session, company_id, headers)

    response = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 20008,
            "message": {
                "message_id": 8,
                "chat": {"id": 700001},
                "text": "hello",
            },
        },
        headers=_webhook_headers(),
    )
    assert response.json() == {"status": "no_connection"}

    result = await db_session.execute(
        select(TelegramConnection).where(TelegramConnection.company_id == company_id)
    )
    connection = result.scalar_one()
    assert connection.status == "pending_chat_id"
    assert connection.telegram_chat_id is None


@pytest.mark.asyncio
async def test_pairing_code_binds_only_its_connection_and_company(
    client, db_session, _setup_company_and_user
):
    first_company_id, _, headers = _setup_company_and_user
    first_pairing = await _request_pairing(
        client, db_session, first_company_id, headers
    )

    other_company = Company(
        id=uuid4(),
        name="Other Pairing Company",
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )
    db_session.add(other_company)
    await db_session.flush()

    first_connection_result = await db_session.execute(
        select(TelegramConnection).where(
            TelegramConnection.company_id == first_company_id
        )
    )
    first_connection = first_connection_result.scalar_one()
    other_connection = TelegramConnection(
        id=uuid4(),
        company_id=other_company.id,
        bot_username="testbot",
        telegram_chat_id=None,
        connected_by=first_connection.connected_by,
        status="pending_chat_id",
    )
    db_session.add(other_connection)
    await db_session.flush()
    await create_pairing(
        db_session,
        connection=other_connection,
        company_id=other_company.id,
        user_id=first_connection.connected_by,
    )

    response = await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20009, 800001, first_pairing["pairing_code"]),
        headers=_webhook_headers(),
    )
    assert response.json() == {"status": "connected"}
    assert first_connection.telegram_chat_id == 800001
    assert first_connection.status == "active"
    assert other_connection.telegram_chat_id is None
    assert other_connection.status == "pending_chat_id"


@pytest.mark.asyncio
async def test_webhook_secret_required_outside_explicit_local_development(
    client, monkeypatch
):
    monkeypatch.setattr(telegram_api.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(telegram_api.settings, "TELEGRAM_WEBHOOK_SECRET", "")

    missing_config = await client.post(
        "/api/v1/telegram/webhook",
        json={"update_id": 20010},
    )
    assert missing_config.status_code == 503

    monkeypatch.setattr(
        telegram_api.settings, "TELEGRAM_WEBHOOK_SECRET", FAKE_WEBHOOK_SECRET
    )
    missing = await client.post(
        "/api/v1/telegram/webhook",
        json={"update_id": 20011},
    )
    incorrect = await client.post(
        "/api/v1/telegram/webhook",
        json={"update_id": 20012},
        headers=_webhook_headers("wrong-secret"),
    )
    valid = await client.post(
        "/api/v1/telegram/webhook",
        json={"update_id": 20013},
        headers=_webhook_headers(),
    )
    assert missing.status_code == 403
    assert incorrect.status_code == 403
    assert valid.status_code == 200


@pytest.mark.asyncio
async def test_explicit_local_development_webhook_bypass(client, monkeypatch):
    monkeypatch.setattr(telegram_api.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(telegram_api.settings, "TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(
        telegram_api.settings, "TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK", True
    )
    response = await client.post(
        "/api/v1/telegram/webhook",
        json={"update_id": 20014},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cross_company_extract_callback_is_denied(
    db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=900001,
        connected_by=user_id,
        status="active",
    )
    other_company = Company(
        id=uuid4(),
        name="Other Extract Company",
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )
    db_session.add_all([connection, other_company])
    await db_session.flush()
    other_item = InboxItem(
        id=uuid4(),
        company_id=other_company.id,
        source="web_text",
        content_type="text",
        original_text="private",
        status="received",
    )
    db_session.add(other_item)
    await db_session.flush()

    dispatched = []
    original_delay = telegram_api.run_ai_extraction.delay
    telegram_api.run_ai_extraction.delay = lambda item_id: dispatched.append(item_id)
    try:
        result = await telegram_api._handle_callback_query(
            {
                "id": "extract-cross-company",
                "data": f"extract:{other_item.id}",
                "message": {"chat": {"id": 900001}, "message_id": 1},
            },
            db_session,
        )
    finally:
        telegram_api.run_ai_extraction.delay = original_delay

    assert result == {"status": "ok"}
    assert dispatched == []
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "telegram.callback_extract")
    )
    audit = audit_result.scalar_one()
    assert audit.company_id == company_id
    assert audit.after_data["status"] == "denied"


@pytest.mark.asyncio
async def test_legacy_approval_callback_is_denied_and_audited(
    db_session, _setup_company_and_user
):
    from app.models.account import Account
    from app.models.draft_transaction import DraftTransaction

    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=905001,
        connected_by=user_id,
        status="active",
    )
    expense_account = Account(
        id=uuid4(),
        company_id=company_id,
        code="5990",
        name_en="Callback Expense",
        type="expense",
        subtype="general",
        is_active=True,
    )
    payment_account = Account(
        id=uuid4(),
        company_id=company_id,
        code="1090",
        name_en="Callback Cash",
        type="asset",
        subtype="cash",
        is_active=True,
    )
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        type="expense",
        amount=10,
        currency="USD",
        transaction_date=datetime.now(UTC).date(),
        description="Approve me",
        category_account_id=expense_account.id,
        payment_account_id=payment_account.id,
        status="ready_for_review",
    )
    db_session.add_all([connection, expense_account, payment_account, draft])
    await db_session.flush()

    result = await telegram_api._handle_callback_query(
        {
            "id": "approve-valid",
            "data": f"approve:{draft.id}",
            "message": {"chat": {"id": 905001}, "message_id": 2},
        },
        db_session,
    )
    assert result == {"status": "ok"}
    assert draft.status == "ready_for_review"

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "telegram.callback_approve")
    )
    assert audit_result.scalar_one().after_data["status"] == "denied"


@pytest.mark.asyncio
async def test_legacy_reject_callback_is_denied_and_audited(
    db_session, _setup_company_and_user
):
    from app.models.draft_transaction import DraftTransaction

    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=910001,
        connected_by=user_id,
        status="active",
    )
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        type="expense",
        amount=10,
        currency="USD",
        transaction_date=datetime.now(UTC).date(),
        description="Reject me",
        status="ready_for_review",
    )
    db_session.add_all([connection, draft])
    await db_session.flush()

    result = await telegram_api._handle_callback_query(
        {
            "id": "reject-valid",
            "data": f"reject:{draft.id}",
            "message": {"chat": {"id": 910001}, "message_id": 2},
        },
        db_session,
    )
    assert result == {"status": "ok"}
    assert draft.status == "ready_for_review"

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "telegram.callback_reject")
    )
    assert audit_result.scalar_one().after_data["status"] == "denied"


@pytest.mark.asyncio
async def test_confirm_callback_marks_ready_without_posting_and_deduplicates(
    client, db_session, _setup_company_and_user
):
    from app.models.draft_transaction import DraftTransaction
    from app.models.journal import JournalEntry

    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=915001,
        connected_by=user_id,
        status="active",
    )
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        type="expense",
        amount=10,
        currency="USD",
        transaction_date=datetime.now(UTC).date(),
        description="Confirm me",
        status="needs_clarification",
    )
    db_session.add_all([connection, draft])
    await db_session.flush()
    payload = {
        "update_id": 30001,
        "callback_query": {
            "id": "confirm-valid",
            "data": f"confirm:{draft.id}",
            "message": {"chat": {"id": 915001}, "message_id": 3},
        },
    }

    first = await client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers=_webhook_headers(),
    )
    replay = await client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers=_webhook_headers(),
    )

    assert first.status_code == 200
    assert first.json() == {"status": "ok"}
    assert replay.json() == {"status": "duplicate"}
    assert draft.status == "ready_for_review"
    entries = (await db_session.execute(select(JournalEntry))).scalars().all()
    assert entries == []
    updates = (
        (
            await db_session.execute(
                select(TelegramUpdate).where(
                    TelegramUpdate.telegram_update_id == payload["update_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(updates) == 1


@pytest.mark.asyncio
async def test_field_edit_updates_existing_draft_without_rerunning_extraction(
    client, db_session, _setup_company_and_user, monkeypatch
):
    from app.models.draft_transaction import DraftTransaction
    from app.services.telegram_edit_state import TelegramEditState

    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=920001,
        connected_by=user_id,
        status="active",
    )
    item = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source="telegram",
        content_type="text",
        original_text="Wrong details",
        detected_language="en",
        status="review_required",
        content_hash="a" * 64,
        duplicate_status="unique",
    )
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        inbox_item_id=item.id,
        type="expense",
        amount=10,
        currency="USD",
        transaction_date=datetime.now(UTC).date(),
        description="Needs correction",
        status="ready_for_review",
    )
    original_update = TelegramUpdate(
        id=uuid4(),
        connection_id=connection.id,
        telegram_update_id=30002,
        message_id=4,
        chat_id=920001,
        update_type="message",
        payload={"update_id": 30002},
        processing_status="processed",
        inbox_item_id=item.id,
    )
    db_session.add_all([connection, item, draft, original_update])
    await db_session.flush()
    state = None

    async def fake_set(next_state):
        nonlocal state
        state = next_state

    async def fake_get(**scope):
        if state and (
            state.connection_id == scope["connection_id"]
            and state.company_id == scope["company_id"]
            and state.chat_id == scope["chat_id"]
        ):
            return state
        return None

    async def fake_clear(**scope):
        nonlocal state
        if state and (
            state.connection_id == scope["connection_id"]
            and state.company_id == scope["company_id"]
            and state.chat_id == scope["chat_id"]
        ):
            state = None

    monkeypatch.setattr(telegram_api, "set_edit_state", fake_set)
    monkeypatch.setattr(telegram_api, "get_edit_state", fake_get)
    monkeypatch.setattr(telegram_api, "clear_edit_state", fake_clear)
    dispatched = []
    monkeypatch.setattr(
        telegram_api.run_ai_extraction,
        "delay",
        lambda inbox_id: dispatched.append(inbox_id),
    )

    correction_request = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 30004,
            "callback_query": {
                "id": "edit-valid",
                "data": f"edit:amount:{draft.id}",
                "message": {"chat": {"id": 920001}, "message_id": 4},
            },
        },
        headers=_webhook_headers(),
    )
    assert correction_request.status_code == 200
    assert isinstance(state, TelegramEditState)
    assert state.draft_id == str(draft.id)
    assert state.field == "amount"

    response = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 30003,
            "message": {
                "message_id": 5,
                "chat": {"id": 920001},
                "text": "12.3456",
            },
        },
        headers=_webhook_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "draft_updated"}
    await db_session.refresh(draft)
    assert str(draft.amount) == "12.3456"
    assert item.original_text == "Wrong details"
    assert item.status == "review_required"
    assert draft.status == "ready_for_review"
    assert dispatched == []
    assert state is None
    items = (
        (
            await db_session.execute(
                select(InboxItem).where(InboxItem.company_id == company_id)
            )
        )
        .scalars()
        .all()
    )
    assert items == [item]


@pytest.mark.asyncio
async def test_invalid_telegram_edit_stays_recoverable_and_cancel_changes_nothing(
    client, db_session, _setup_company_and_user, monkeypatch
):
    from app.models.draft_transaction import DraftTransaction

    company_id, user_id, _ = _setup_company_and_user
    connection = TelegramConnection(
        id=uuid4(),
        company_id=company_id,
        bot_username="testbot",
        telegram_chat_id=920101,
        connected_by=user_id,
        status="active",
    )
    draft = DraftTransaction(
        id=uuid4(),
        company_id=company_id,
        type="expense",
        amount=10,
        currency="USD",
        transaction_date=datetime.now(UTC).date(),
        description="Unchanged",
        status="needs_clarification",
    )
    db_session.add_all([connection, draft])
    await db_session.flush()
    state = None

    async def fake_set(next_state):
        nonlocal state
        state = next_state

    async def fake_get(**scope):
        return state

    async def fake_clear(**scope):
        nonlocal state
        state = None

    monkeypatch.setattr(telegram_api, "set_edit_state", fake_set)
    monkeypatch.setattr(telegram_api, "get_edit_state", fake_get)
    monkeypatch.setattr(telegram_api, "clear_edit_state", fake_clear)

    selected = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 30101,
            "callback_query": {
                "id": "edit-currency",
                "data": f"edit:currency:{draft.id}",
                "message": {"chat": {"id": 920101}, "message_id": 8},
            },
        },
        headers=_webhook_headers(),
    )
    assert selected.status_code == 200

    invalid = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 30102,
            "message": {
                "message_id": 9,
                "chat": {"id": 920101},
                "text": "not-currency",
            },
        },
        headers=_webhook_headers(),
    )
    assert invalid.status_code == 200
    assert invalid.json() == {"status": "edit_validation_failed"}
    assert state is not None
    assert draft.currency == "USD"

    cancelled = await client.post(
        "/api/v1/telegram/webhook",
        json={
            "update_id": 30103,
            "callback_query": {
                "id": "edit-cancel",
                "data": f"edit_cancel:{draft.id}",
                "message": {"chat": {"id": 920101}, "message_id": 8},
            },
        },
        headers=_webhook_headers(),
    )
    assert cancelled.status_code == 200
    assert state is None
    assert draft.currency == "USD"


@pytest.mark.asyncio
async def test_pairing_audit_records_never_contain_raw_code(
    client, db_session, _setup_company_and_user
):
    company_id, _, headers = _setup_company_and_user
    pairing = await _request_pairing(client, db_session, company_id, headers)
    raw_code = pairing["pairing_code"]

    await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20015, 920001, raw_code),
        headers=_webhook_headers(),
    )
    await client.post(
        "/api/v1/telegram/webhook",
        json=_start_update(20016, 920002, raw_code),
        headers=_webhook_headers(),
    )

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.action.like("telegram.pairing_%"))
    )
    logs = audit_result.scalars().all()
    assert {log.action for log in logs} >= {
        "telegram.pairing_created",
        "telegram.pairing_succeeded",
        "telegram.pairing_failed",
    }
    for log in logs:
        serialized = json.dumps(
            {
                "entity_id": log.entity_id,
                "before": log.before_data,
                "after": log.after_data,
            },
            default=str,
        )
        assert raw_code not in serialized
