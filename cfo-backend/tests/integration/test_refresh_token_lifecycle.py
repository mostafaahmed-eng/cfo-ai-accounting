import re

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth import token_fingerprint


async def _setup_password(db_session, user_id):
    user = (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one()
    user.password_hash = hash_password("testpass123")
    await db_session.flush()
    return user


async def _login(client, email, password="testpass123"):
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_refresh_lifecycle_rotate_reuse_logout(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    user = await _setup_password(db_session, user_id)

    login = await _login(client, user.email)
    access = login["access_token"]
    refresh = login["refresh_token"]
    assert refresh

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert me.status_code == 200

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200, rotated.text
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh and new_refresh != refresh

    # Replaying the already-rotated token is treated as reuse: 401 and the
    # whole family (including the freshly issued token) is revoked.
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401

    family_dead = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_refresh}
    )
    assert family_dead.status_code == 401

    # A fresh login starts a new family; logout revokes it server-side.
    login2 = await _login(client, user.email)
    access2 = login2["access_token"]
    refresh2 = login2["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {access2}"}
    )
    assert logout.status_code == 200

    after_logout = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh2}
    )
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_password_change_revokes_access_and_refresh_tokens(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    user = await _setup_password(db_session, user_id)

    login = await _login(client, user.email)
    access = login["access_token"]
    refresh = login["refresh_token"]

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "current_password": "testpass123",
            "new_password": "NewPassword123",
        },
    )
    assert changed.status_code == 200, changed.text

    # token_version bump kills the old access token immediately.
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert me.status_code == 401

    refresh_dead = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh}
    )
    assert refresh_dead.status_code == 401

    # The new password signs in and mints a working family.
    relogin = await _login(client, user.email, password="NewPassword123")
    me_ok = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {relogin['access_token']}"},
    )
    assert me_ok.status_code == 200


@pytest.mark.asyncio
async def test_stored_refresh_token_is_hashed_not_plaintext(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    user = await _setup_password(db_session, user_id)

    login = await _login(client, user.email)
    refresh = login["refresh_token"]

    rows = (await db_session.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user.id
    assert row.token_hash != refresh
    assert len(row.token_hash) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", row.token_hash)
    assert row.token_hash == token_fingerprint(refresh)
    assert row.revoked_at is None


@pytest.mark.asyncio
async def test_rotated_token_chain_is_recorded(
    client, db_session, _setup_company_and_user
):
    company_id, user_id, _ = _setup_company_and_user
    user = await _setup_password(db_session, user_id)

    login = await _login(client, user.email)
    refresh = login["refresh_token"]

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200

    rows = (
        (
            await db_session.execute(
                select(RefreshToken).order_by(RefreshToken.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    original, successor = rows
    assert original.revoked_at is not None
    assert original.replaced_by_id == successor.id
    assert successor.revoked_at is None
