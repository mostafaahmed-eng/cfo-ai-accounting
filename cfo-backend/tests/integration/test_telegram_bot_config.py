import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

import app.core.crypto as crypto_module
from app.api.v1 import integrations as integrations_api
from app.models.telegram import TelegramBotConfig
from app.services.telegram_bot_config import save_telegram_config

FAKE_TOKEN = "123456789:AAfake-token-for-tests"

_FAKE_FERNET = Fernet(Fernet.generate_key())


@pytest.fixture(autouse=True)
def _stub_fernet(monkeypatch):
    monkeypatch.setattr(crypto_module, "_fernet", lambda: _FAKE_FERNET)


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


async def test_put_bot_config_rejects_invalid_token(
    client, db_session, _setup_company_and_user, monkeypatch
):
    _, _, headers = _setup_company_and_user
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
    client, db_session, _setup_company_and_user, monkeypatch
):
    _, _, headers = _setup_company_and_user
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
    client, db_session, _setup_company_and_user, monkeypatch
):
    _, _, headers = _setup_company_and_user
    monkeypatch.setattr(integrations_api, "_telegram_get_me", _fake_get_me_ok)
    response = await client.put(
        "/api/v1/integrations/telegram/bot-config",
        headers=headers,
        json={"bot_token": FAKE_TOKEN, "bot_username": "myhandpicked"},
    )
    assert response.status_code == 200
    assert response.json()["bot_username"] == "myhandpicked"


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
