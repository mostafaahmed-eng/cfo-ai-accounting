from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.document import Document


@pytest.mark.asyncio
async def test_password_change_is_audited(client, db_session, _setup_company_and_user):
    company_id, user_id, headers = _setup_company_and_user
    resp = await client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "testpass123",
            "new_password": "NewPassword1",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "auth.password_changed",
            AuditLog.entity_id == str(user_id),
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    payload = f"{rows[0].before_data}{rows[0].after_data}"
    # The audit payload must never contain any password.
    assert "testpass123" not in payload
    assert "NewPassword1" not in payload
    # Old session tokens were revoked (token_version bumped).
    assert rows[0].after_data.get("token_version", 0) >= 1


@pytest.mark.asyncio
async def test_document_upload_is_audited(
    client, db_session, _setup_company_and_user, monkeypatch
):
    import app.api.v1.documents as documents_mod

    company_id, user_id, headers = _setup_company_and_user
    headers = {**headers, "X-Company-ID": str(company_id)}

    async def fake_store(
        db,
        company_id=None,
        validated=None,
        original_name=None,
        source=None,
        source_reference=None,
        submitted_by=None,
    ):
        doc = Document(
            id=uuid4(),
            company_id=str(company_id),
            storage_key="test/intake.pdf",
            original_name=original_name or "intake.pdf",
            mime_type="application/pdf",
            size_bytes=5,
            sha256_hash="f" * 64,
            document_type="receipt",
            upload_status="stored",
            uploaded_by=submitted_by,
        )
        db.add(doc)
        await db.flush()
        return SimpleNamespace(document=doc, dispatch_processing=False)

    async def fake_validate(file):
        return SimpleNamespace(extension="pdf")

    monkeypatch.setattr(documents_mod, "validate_upload", fake_validate)
    monkeypatch.setattr(documents_mod, "store_document_intake", fake_store)

    resp = await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("intake.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "document.uploaded")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].entity_id == str(resp.json()["id"])


@pytest.mark.asyncio
async def test_document_delete_is_audited(
    client, db_session, _setup_company_and_user, monkeypatch
):
    import app.api.v1.documents as documents_mod

    company_id, user_id, headers = _setup_company_and_user
    headers = {**headers, "X-Company-ID": str(company_id)}

    async def fake_delete(key):
        return None

    fake_client = SimpleNamespace(delete_file=fake_delete)
    monkeypatch.setattr(documents_mod, "storage_client", fake_client)

    doc = Document(
        id=uuid4(),
        company_id=str(company_id),
        storage_key="test/delete.pdf",
        original_name="delete.pdf",
        mime_type="application/pdf",
        size_bytes=7,
        sha256_hash="e" * 64,
        document_type="receipt",
        upload_status="stored",
        uploaded_by=user_id,
    )
    db_session.add(doc)
    await db_session.flush()

    resp = await client.delete(f"/api/v1/documents/{doc.id}", headers=headers)
    assert resp.status_code == 200

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "document.deleted")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].entity_id == str(doc.id)
    assert rows[0].before_data.get("original_name") == "delete.pdf"
