import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import async_session
from app.main import app
from app.models.audit_log import AuditLog


@pytest.mark.asyncio
async def test_failed_login_audit_survives_real_transaction_rollback(_engine):
    """A failed login audit row must persist even though the request session
    is rolled back when the handler raises HTTPException 401.

    This exercises the production path end-to-end (the real get_db dependency,
    which commits on success and rolls back on any exception), then verifies
    the audit row was committed independently and is visible on a fresh
    connection.
    """
    app.dependency_overrides.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/login",
            json={"email": "ghost-user@example.com", "password": "wrong-pass"},
        )
    assert response.status_code == 401

    async with async_session() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "auth.login_failed",
                AuditLog.entity_id == "ghost-user@example.com",
            )
        )
        rows = result.scalars().all()
    assert len(rows) >= 1
    assert all(row.user_id is None for row in rows)
    # The audit payload must never include the submitted password.
    for row in rows:
        assert "wrong-pass" not in str(row.after_data or {})
        assert "wrong-pass" not in str(row.before_data or {})
