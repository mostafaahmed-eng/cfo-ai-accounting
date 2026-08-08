from datetime import UTC, datetime
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

import app.core.crypto as crypto_module
import app.dependencies as deps_module
from app.api.v1 import integrations as integrations_api
from app.config import Settings
from app.core.security import hash_password
from app.models.company import Company, CompanyMember
from app.models.telegram import TelegramBotConfig
from app.models.user import User
from app.services.auth import create_access_token
from app.services.telegram_bot_config import save_telegram_config

FAKE_TOKEN = "123456789:AAfake-token-for-tests"

_FAKE_FERNET = Fernet(Fernet.generate_key())


@pytest.fixture(autouse=True)
def _stub_fernet(monkeypatch):
    monkeypatch.setattr(crypto_module, "_fernet", lambda: _FAKE_FERNET)


@pytest.fixture(autouse=True)
def _clear_platform_admin_settings(monkeypatch):
    monkeypatch.setattr(
        deps_module,
        "get_settings",
        lambda: Settings(PLATFORM_ADMIN_EMAILS="", _env_file=None),
    )


@pytest.fixture
def _set_platform_admin(monkeypatch):
    def _apply(email: str):
        monkeypatch.setattr(
            deps_module,
            "get_settings",
            lambda: Settings(PLATFORM_ADMIN_EMAILS=email, _env_file=None),
        )

    return _apply


async def _fake_get_me_ok(*args, **kwargs):
    return {
        "ok": True,
        "result": {
            "id": 123456789,
            "is_bot": True,
            "first_name": "TestBot",
            "username": "storedbot",
        },
    }


async def _failed_get_me(*args, **kwargs):
    return {"ok": False, "description": "Unauthorized"}


async def _make_user(
    db_session,
    email: str,
    role: str = "OWNER",
    company_name: str = "Test Company",
):
    user_id = uuid4()
    company_id = uuid4()

    user = User(
        id=user_id,
        email=email,
        name="Test User",
        password_hash=hash_password("testpass123"),
        language="en",
        timezone="UTC",
        status="active",
    )
    company = Company(
        id=company_id,
        name=company_name,
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )
    member = CompanyMember(
        id=uuid4(),
        company_id=str(company_id),
        user_id=str(user_id),
        role=role,
        status="active",
        joined_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db_session.add_all([user, company, member])
    await db_session.flush()

    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}
    return company_id, user_id, headers


# ---------------------------------------------------------------------------
# GET bot-config (authenticated only; returns no secrets)
# ---------------------------------------------------------------------------


async def test_get_bot_config_requires_auth(client):
    response = await client.get("/api/v1/integrations/telegram/bot-config")
    assert response.status_code == 401


async def test_get_bot_config_unconfigured(client, _setup_company_and_user):
    _, _, headers = _setup_company_and_user
    response = await client.get(
        "/api/v1/integrations/telegram/bot-config", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["configured"] is False


async def test_get_bot_config_never_returns_the_token(client, db_session):
    company_id, user_id, headers = await _make_user(
        db_session, "someone@example.com", role="VIEWER"
    )
    await save_telegram_config(
        db_session,
        bot_token=FAKE_TOKEN,
        bot_username="storedbot",
        updated_by=user_id,
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/integrations/telegram/bot-config", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["has_token"] is True
    assert "bot_token" not in body
    assert "webhook_secret" not in body
    assert FAKE_TOKEN not in response.text


# ---------------------------------------------------------------------------
# PUT bot-config: only an explicitly listed platform administrator may modify
# the GLOBAL bot configuration. Per-company roles never grant this.
# ---------------------------------------------------------------------------


async def test_put_bot_config_requires_auth(client):
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        json={"bot_token": FAKE_TOKEN, "bot_username": ""},
    )
    assert response.status_code == 401


async def test_put_bot_config_rejected_for_company_admin(client, db_session):
    _, _, headers = await _make_user(
        db_session, "admin-not-listed@example.com", role="ADMIN"
    )
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": ""},
    )
    assert response.status_code == 403


async def test_put_bot_config_rejected_for_company_owner(client, db_session):
    _, _, headers = await _make_user(
        db_session, "owner-not-listed@example.com", role="OWNER"
    )
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": ""},
    )
    assert response.status_code == 403


async def test_put_bot_config_rejected_for_other_tenant_user(
    client, db_session, _set_platform_admin
):
    # A user from company B is not implicitly authorized, even as OWNER.
    _set_platform_admin("platform-owner@example.com")
    _, _, headers = await _make_user(
        db_session,
        "other-tenant-owner@example.com",
        role="OWNER",
        company_name="Other Company",
    )
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": ""},
    )
    assert response.status_code == 403


async def test_put_bot_config_rejected_when_allowlist_empty(
    client, db_session, monkeypatch
):
    # With PLATFORM_ADMIN_EMAILS unset, no one may change the global config.
    _, _, headers = await _make_user(db_session, "anyone@example.com", role="OWNER")
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": ""},
    )
    assert response.status_code == 403


async def test_put_bot_config_rejects_invalid_token(
    client, db_session, _set_platform_admin, monkeypatch
):
    _set_platform_admin("platform-owner@example.com")
    _, _, headers = await _make_user(
        db_session, "platform-owner@example.com", role="OWNER"
    )
    monkeypatch.setattr(
        integrations_api,
        "_telegram_get_me",
        lambda token: _failed_get_me(),
    )
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": ""},
    )
    assert response.status_code == 422


async def test_put_and_get_bot_config(
    client, db_session, _set_platform_admin, monkeypatch
):
    _set_platform_admin("platform-owner@example.com")
    _, _, headers = await _make_user(
        db_session, "platform-owner@example.com", role="OWNER"
    )
    monkeypatch.setattr(integrations_api, "_telegram_get_me", _fake_get_me_ok)
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": ""},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["bot_username"] == "storedbot"
    assert body["verified_username"] == "storedbot"
    assert body["has_token"] is True

    row = await db_session.execute(select(TelegramBotConfig))
    config = row.scalar_one()
    assert config.bot_token == FAKE_TOKEN
    assert config.webhook_secret

    get_response = await client.get(
        "/api/v1/integrations/telegram/bot-config", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["bot_username"] == "storedbot"


async def test_put_keeps_manual_username(
    client, db_session, _set_platform_admin, monkeypatch
):
    _set_platform_admin("platform-owner@example.com")
    _, _, headers = await _make_user(
        db_session, "platform-owner@example.com", role="OWNER"
    )
    monkeypatch.setattr(integrations_api, "_telegram_get_me", _fake_get_me_ok)
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": "myhandpicked"},
    )
    assert response.status_code == 200
    assert response.json()["bot_username"] == "myhandpicked"


# ---------------------------------------------------------------------------
# Existing behavior that must keep working
# ---------------------------------------------------------------------------


async def test_connect_uses_stored_username(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, headers = _setup_company_and_user
    await save_telegram_config(
        db_session,
        bot_token=FAKE_TOKEN,
        bot_username="storedbot",
        updated_by=user_id,
    )
    await db_session.flush()

    response = await client.post(
        "/api/v1/integrations/telegram/connect",
        headers={**headers, "X-Company-ID": str(company_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bot_username"] == "storedbot"
    assert (
        body["pairing_link"] == f"https://t.me/storedbot?start={body['pairing_code']}"
    )


async def test_webhook_uses_stored_secret(
    client, db_session, _setup_company_and_user, monkeypatch
):
    _, user_id, headers = _setup_company_and_user
    await save_telegram_config(
        db_session,
        bot_token=FAKE_TOKEN,
        bot_username="storedbot",
        webhook_secret="stored-secret-123",
        updated_by=user_id,
    )
    await db_session.flush()

    payload = {"update_id": 990099}
    good = await client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "stored-secret-123"},
    )
    assert good.status_code == 200

    bad = await client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert bad.status_code == 403
