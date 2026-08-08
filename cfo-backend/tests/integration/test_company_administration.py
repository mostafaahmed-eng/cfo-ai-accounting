import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserStatus
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyMember
from app.models.invitation import Invitation
from app.models.user import User
from app.services.auth import create_access_token
from app.services.company_authorization import authorize_member_update

pytestmark = pytest.mark.asyncio


def _headers(user_id, company_id=None):
    headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}
    if company_id is not None:
        headers["X-Company-ID"] = str(company_id)
    return headers


def _user(email):
    return User(
        id=uuid4(),
        email=email,
        name=email.split("@")[0],
        password_hash="unused",
        language="en",
        timezone="UTC",
        status=UserStatus.active,
    )


def _company(name):
    return Company(
        id=uuid4(),
        name=name,
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )


def _membership(user, company, role, membership_status="active"):
    return CompanyMember(
        id=uuid4(),
        user_id=user.id,
        company_id=company.id,
        role=role,
        status=membership_status,
        joined_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


async def _administration_fixture(db_session):
    company = _company(f"Admin Co {uuid4().hex[:6]}")
    owner = _user(f"owner-{uuid4().hex[:6]}@example.com")
    admin = _user(f"admin-{uuid4().hex[:6]}@example.com")
    member = _user(f"member-{uuid4().hex[:6]}@example.com")
    owner_membership = _membership(owner, company, "OWNER")
    admin_membership = _membership(admin, company, "ADMIN")
    member_membership = _membership(member, company, "ACCOUNTANT")
    db_session.add_all(
        [
            company,
            owner,
            admin,
            member,
            owner_membership,
            admin_membership,
            member_membership,
        ]
    )
    await db_session.flush()
    return (
        company,
        owner,
        admin,
        member,
        owner_membership,
        admin_membership,
        member_membership,
    )


async def test_member_cannot_invite_or_modify_membership(client, db_session):
    company, _, _, member, _, admin_membership, _ = await _administration_fixture(
        db_session
    )
    headers = _headers(member.id)

    invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "blocked@example.com", "role": "VIEWER"},
        headers=headers,
    )
    update = await client.patch(
        f"/api/v1/companies/{company.id}/members/{admin_membership.id}",
        json={"status": "disabled"},
        headers=headers,
    )

    assert invite.status_code == 403
    assert update.status_code == 403
    assert invite.json()["detail"] == "Company administrator access required"
    assert update.json()["detail"] == "Company administrator access required"


async def test_admin_can_invite_and_update_non_owner(client, db_session):
    company, _, admin, _, _, _, member_membership = await _administration_fixture(
        db_session
    )
    headers = _headers(admin.id)

    invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "new-administered@example.com", "role": "VIEWER"},
        headers=headers,
    )
    update = await client.patch(
        f"/api/v1/companies/{company.id}/members/{member_membership.id}",
        json={"role": "APPROVER", "status": "disabled"},
        headers=headers,
    )

    assert invite.status_code == 200
    assert update.status_code == 200
    assert update.json()["role"] == "APPROVER"
    assert update.json()["status"] == "disabled"


async def test_admin_cannot_modify_owner_or_grant_owner(client, db_session):
    (
        company,
        _,
        admin,
        _,
        owner_membership,
        _,
        member_membership,
    ) = await _administration_fixture(db_session)
    headers = _headers(admin.id)

    modify_owner = await client.patch(
        f"/api/v1/companies/{company.id}/members/{owner_membership.id}",
        json={"status": "disabled"},
        headers=headers,
    )
    grant_owner = await client.patch(
        f"/api/v1/companies/{company.id}/members/{member_membership.id}",
        json={"role": "OWNER"},
        headers=headers,
    )
    owner_invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "owner-invite@example.com", "role": "OWNER"},
        headers=headers,
    )

    assert modify_owner.status_code == 403
    assert grant_owner.status_code == 403
    assert owner_invite.status_code == 422


async def test_owner_can_promote_and_demote_when_another_owner_remains(
    client, db_session
):
    (
        company,
        owner,
        _,
        _,
        owner_membership,
        admin_membership,
        _,
    ) = await _administration_fixture(db_session)
    headers = _headers(owner.id)

    promote = await client.patch(
        f"/api/v1/companies/{company.id}/members/{admin_membership.id}",
        json={"role": "OWNER"},
        headers=headers,
    )
    demote_self = await client.patch(
        f"/api/v1/companies/{company.id}/members/{owner_membership.id}",
        json={"role": "ADMIN"},
        headers=headers,
    )

    assert promote.status_code == 200
    assert demote_self.status_code == 200
    assert demote_self.json()["role"] == "ADMIN"


@pytest.mark.parametrize(
    "payload",
    [{"role": "ADMIN"}, {"status": "disabled"}],
)
async def test_last_active_owner_cannot_be_changed(client, db_session, payload):
    company = _company(f"Last Owner {uuid4().hex[:6]}")
    owner = _user(f"last-owner-{uuid4().hex[:6]}@example.com")
    membership = _membership(owner, company, "OWNER")
    db_session.add_all([company, owner, membership])
    await db_session.flush()

    response = await client.patch(
        f"/api/v1/companies/{company.id}/members/{membership.id}",
        json=payload,
        headers=_headers(owner.id),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "The last active owner cannot be changed"


async def test_concurrent_owner_changes_cannot_remove_every_owner(_engine):
    company = _company(f"Concurrent Owners {uuid4().hex[:6]}")
    first_user = _user(f"concurrent-one-{uuid4().hex[:6]}@example.com")
    second_user = _user(f"concurrent-two-{uuid4().hex[:6]}@example.com")
    first = _membership(first_user, company, "OWNER")
    second = _membership(second_user, company, "OWNER")

    async with AsyncSession(_engine, expire_on_commit=False) as setup:
        setup.add_all([company, first_user, second_user, first, second])
        await setup.commit()

    async def demote(membership_id):
        async with AsyncSession(_engine, expire_on_commit=False) as session:
            async with session.begin():
                target = (
                    await session.execute(
                        select(CompanyMember).where(CompanyMember.id == membership_id)
                    )
                ).scalar_one()
                await authorize_member_update(
                    session,
                    actor=target,
                    target=target,
                    new_role="ADMIN",
                    new_status=None,
                )
                target.role = "ADMIN"

    results = await asyncio.gather(
        demote(first.id),
        demote(second.id),
        return_exceptions=True,
    )

    async with AsyncSession(_engine, expire_on_commit=False) as verify:
        owner_count = len(
            (
                await verify.execute(
                    select(CompanyMember).where(
                        CompanyMember.company_id == company.id,
                        CompanyMember.role == "OWNER",
                        CompanyMember.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert owner_count == 1
        assert sum(not isinstance(result, Exception) for result in results) == 1

        await verify.execute(
            delete(CompanyMember).where(CompanyMember.company_id == company.id)
        )
        await verify.execute(
            delete(User).where(User.id.in_([first_user.id, second_user.id]))
        )
        await verify.execute(delete(Company).where(Company.id == company.id))
        await verify.commit()


async def test_cross_company_membership_and_invitation_operations_fail(
    client, db_session
):
    company, owner, _, _, _, _, member_membership = await _administration_fixture(
        db_session
    )
    other = _company(f"Other {uuid4().hex[:6]}")
    db_session.add(other)
    await db_session.flush()

    invite = await client.post(
        f"/api/v1/companies/{other.id}/invitations",
        json={"email": "hidden@example.com", "role": "VIEWER"},
        headers=_headers(owner.id),
    )
    update = await client.patch(
        f"/api/v1/companies/{other.id}/members/{member_membership.id}",
        json={"status": "disabled"},
        headers=_headers(owner.id),
    )

    assert invite.status_code == 403
    assert update.status_code == 403
    invitations = await db_session.execute(
        select(Invitation).where(Invitation.company_id == other.id)
    )
    assert invitations.scalars().all() == []


async def test_inactive_admin_cannot_administer(client, db_session):
    company = _company(f"Inactive {uuid4().hex[:6]}")
    admin = _user(f"inactive-{uuid4().hex[:6]}@example.com")
    target = _user(f"target-{uuid4().hex[:6]}@example.com")
    admin_membership = _membership(admin, company, "ADMIN", "disabled")
    target_membership = _membership(target, company, "VIEWER")
    db_session.add_all([company, admin, target, admin_membership, target_membership])
    await db_session.flush()

    response = await client.patch(
        f"/api/v1/companies/{company.id}/members/{target_membership.id}",
        json={"role": "ACCOUNTANT"},
        headers=_headers(admin.id, company.id),
    )
    assert response.status_code == 403


async def test_invalid_invitation_role_is_rejected(client, db_session):
    company, owner, *_ = await _administration_fixture(db_session)
    response = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "invalid@example.com", "role": "SUPERUSER"},
        headers=_headers(owner.id),
    )
    assert response.status_code == 422


async def test_administration_audits_exclude_invitation_credentials(client, db_session):
    company, _, admin, _, _, _, member_membership = await _administration_fixture(
        db_session
    )
    invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "audit@example.com", "role": "VIEWER"},
        headers=_headers(admin.id),
    )
    update = await client.patch(
        f"/api/v1/companies/{company.id}/members/{member_membership.id}",
        json={"role": "APPROVER"},
        headers=_headers(admin.id),
    )
    assert invite.status_code == 200
    assert update.status_code == 200

    logs = await db_session.execute(
        select(AuditLog).where(
            AuditLog.company_id == company.id,
            AuditLog.action.in_(["invitation.created", "membership.updated"]),
        )
    )
    serialized = " ".join(str(log.after_data) for log in logs.scalars().all())
    assert "token" not in serialized.lower()
    assert "secret" not in serialized.lower()


async def test_single_company_works_without_explicit_selection(
    client, _setup_company_and_user
):
    _, _, headers = _setup_company_and_user
    response = await client.get("/api/v1/accounts", headers=headers)
    assert response.status_code == 200


async def test_multi_company_requires_authorized_explicit_selection(client, db_session):
    first = _company(f"First {uuid4().hex[:6]}")
    second = _company(f"Second {uuid4().hex[:6]}")
    user = _user(f"multi-{uuid4().hex[:6]}@example.com")
    first_membership = _membership(user, first, "OWNER")
    second_membership = _membership(user, second, "VIEWER")
    first_account = Account(
        id=uuid4(),
        company_id=first.id,
        code="1000",
        name_en="First Cash",
        type="asset",
        subtype="cash",
        is_active=True,
    )
    second_account = Account(
        id=uuid4(),
        company_id=second.id,
        code="2000",
        name_en="Second Payable",
        type="liability",
        subtype="payable",
        is_active=True,
    )
    db_session.add_all(
        [
            first,
            second,
            user,
            first_membership,
            second_membership,
            first_account,
            second_account,
        ]
    )
    await db_session.flush()

    no_selection = await client.get("/api/v1/accounts", headers=_headers(user.id))
    first_response = await client.get(
        "/api/v1/accounts", headers=_headers(user.id, first.id)
    )
    second_response = await client.get(
        "/api/v1/accounts", headers=_headers(user.id, second.id)
    )

    assert no_selection.status_code == 409
    assert no_selection.json()["detail"] == "Explicit company selection required"
    assert [item["name_en"] for item in first_response.json()] == ["First Cash"]
    assert [item["name_en"] for item in second_response.json()] == ["Second Payable"]


@pytest.mark.parametrize(
    ("company_header", "expected_status"),
    [("not-a-uuid", 400), (str(uuid4()), 403)],
)
async def test_invalid_company_selection_fails_safely(
    client, db_session, company_header, expected_status
):
    company = _company(f"Selection {uuid4().hex[:6]}")
    user = _user(f"selection-{uuid4().hex[:6]}@example.com")
    membership = _membership(user, company, "OWNER")
    db_session.add_all([company, user, membership])
    await db_session.flush()

    response = await client.get(
        "/api/v1/accounts",
        headers=_headers(user.id) | {"X-Company-ID": company_header},
    )
    assert response.status_code == expected_status


async def test_inactive_company_selection_fails_safely(client, db_session):
    company = _company(f"Disabled Selection {uuid4().hex[:6]}")
    user = _user(f"disabled-selection-{uuid4().hex[:6]}@example.com")
    membership = _membership(user, company, "OWNER", "disabled")
    db_session.add_all([company, user, membership])
    await db_session.flush()

    response = await client.get(
        "/api/v1/accounts",
        headers=_headers(user.id, company.id),
    )
    assert response.status_code == 403


async def test_company_list_contains_only_current_users_active_memberships(
    client, db_session
):
    active_company = _company(f"Active {uuid4().hex[:6]}")
    disabled_company = _company(f"Disabled {uuid4().hex[:6]}")
    foreign_company = _company(f"Foreign {uuid4().hex[:6]}")
    user = _user(f"list-{uuid4().hex[:6]}@example.com")
    stranger = _user(f"stranger-{uuid4().hex[:6]}@example.com")
    db_session.add_all(
        [
            active_company,
            disabled_company,
            foreign_company,
            user,
            stranger,
            _membership(user, active_company, "ADMIN"),
            _membership(user, disabled_company, "OWNER", "disabled"),
            _membership(stranger, foreign_company, "OWNER"),
        ]
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/companies/memberships",
        headers=_headers(user.id),
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "membership_id": str(
                (
                    await db_session.execute(
                        select(CompanyMember).where(
                            CompanyMember.user_id == user.id,
                            CompanyMember.company_id == active_company.id,
                        )
                    )
                )
                .scalar_one()
                .id
            ),
            "company_id": str(active_company.id),
            "company_name": active_company.name,
            "role": "ADMIN",
        }
    ]


async def test_get_company_detail_scoped_to_membership(client, db_session):
    (
        company,
        owner,
        _,
        member,
        _,
        _,
        _,
    ) = await _administration_fixture(db_session)

    owner_detail = await client.get(
        f"/api/v1/companies/{company.id}",
        headers=_headers(owner.id, company.id),
    )
    member_detail = await client.get(
        f"/api/v1/companies/{company.id}",
        headers=_headers(member.id, company.id),
    )

    assert owner_detail.status_code == 200
    assert owner_detail.json()["id"] == str(company.id)
    assert member_detail.status_code == 200


async def test_get_company_detail_foreign_company_rejected(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    foreign = _company(f"Foreign Detail {uuid4().hex[:6]}")
    stranger = _user(f"stranger-detail-{uuid4().hex[:6]}@example.com")
    db_session.add_all([foreign, stranger])
    await db_session.flush()

    response = await client.get(
        f"/api/v1/companies/{foreign.id}",
        headers=_headers(stranger.id, foreign.id),
    )
    assert response.status_code == 403


async def test_update_company_requires_admin(client, db_session):
    company, _, admin, member, _, _, _ = await _administration_fixture(db_session)

    member_update = await client.patch(
        f"/api/v1/companies/{company.id}",
        json={"name": "Hacked"},
        headers=_headers(member.id, company.id),
    )
    assert member_update.status_code == 403

    valid_update = await client.patch(
        f"/api/v1/companies/{company.id}",
        json={"name": "Renamed Co", "country_code": "CA"},
        headers=_headers(admin.id, company.id),
    )
    assert valid_update.status_code == 200
    assert valid_update.json()["name"] == "Renamed Co"
    assert valid_update.json()["country_code"] == "CA"


async def test_list_company_members_owner_and_admin(client, db_session):
    company, owner, admin, member, _, _, _ = await _administration_fixture(db_session)

    owner_list = await client.get(
        f"/api/v1/companies/{company.id}/members",
        headers=_headers(owner.id, company.id),
    )
    admin_list = await client.get(
        f"/api/v1/companies/{company.id}/members",
        headers=_headers(admin.id, company.id),
    )

    assert owner_list.status_code == 200
    body = owner_list.json()
    assert len(body) == 3
    by_email = {item["email"]: item for item in body}
    assert by_email[owner.email]["role"] == "OWNER"
    assert by_email[owner.email]["status"] == "active"
    assert by_email[admin.email]["role"] == "ADMIN"
    assert by_email[member.email]["role"] == "ACCOUNTANT"
    assert owner_list.headers["X-Total-Count"] == "3"
    assert admin_list.status_code == 200


async def test_list_members_forbidden_for_non_admin(client, db_session):
    company, _, _, member, _, _, _ = await _administration_fixture(db_session)

    response = await client.get(
        f"/api/v1/companies/{company.id}/members",
        headers=_headers(member.id, company.id),
    )
    assert response.status_code == 403


async def test_list_members_requires_auth(client):
    company_id = uuid4()
    response = await client.get(
        f"/api/v1/companies/{company_id}/members",
    )
    assert response.status_code == 401


async def test_list_members_foreign_company_forbidden(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    unaware = _company(f"Unaware {uuid4().hex[:6]}")
    stranger = _user(f"multer-{uuid4().hex[:6]}@example.com")
    stranger_membership = _membership(stranger, unaware, "VIEWER")
    db_session.add_all([unaware, stranger, stranger_membership])
    await db_session.flush()

    response = await client.get(
        f"/api/v1/companies/{company.id}/members",
        headers=_headers(stranger.id, unaware.id),
    )
    assert response.status_code == 403


async def test_list_invitations_shows_pending_and_expired(client, db_session):
    company, owner, admin, _, _, _, _ = await _administration_fixture(db_session)
    invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "guest@example.com", "role": "VIEWER"},
        headers=_headers(owner.id, company.id),
    )
    assert invite.status_code == 200

    response = await client.get(
        f"/api/v1/companies/{company.id}/invitations",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["email"] == "guest@example.com"
    assert body[0]["status"] in ("pending", "expired")
    assert response.headers["X-Total-Count"] == "1"


async def test_list_invitations_forbidden_role(client, db_session):
    company, _, _, member, _, _, _ = await _administration_fixture(db_session)

    response = await client.get(
        f"/api/v1/companies/{company.id}/invitations",
        headers=_headers(member.id, company.id),
    )
    assert response.status_code == 403


async def test_list_invitations_foreign_company(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    other = _company(f"Invites Foreign {uuid4().hex[:6]}")
    other_owner = _user(f"invites-owner-{uuid4().hex[:6]}@example.com")
    db_session.add_all([other, other_owner, _membership(other_owner, other, "OWNER")])
    await db_session.flush()

    response = await client.get(
        f"/api/v1/companies/{other.id}/invitations",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code == 403


async def test_remove_empty_invitation_list(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    response = await client.get(
        f"/api/v1/companies/{company.id}/invitations",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "0"


async def test_remove_member_admin_removes_non_owner(client, db_session):
    company, owner, admin, _, _, _, member_membership = await _administration_fixture(
        db_session
    )

    response = await client.delete(
        f"/api/v1/companies/{company.id}/members/{member_membership.id}",
        headers=_headers(admin.id, company.id),
    )
    assert response.status_code == 200
    remaining = await db_session.execute(
        select(CompanyMember).where(CompanyMember.company_id == company.id)
    )
    ids = [str(m.id) for m in remaining.scalars().all()]
    assert str(member_membership.id) not in ids


async def test_remove_member_forbidden_role(client, db_session):
    company, _, _, member, _, _, other_member = await _administration_fixture(
        db_session
    )

    response = await client.delete(
        f"/api/v1/companies/{company.id}/members/{other_member.id}",
        headers=_headers(member.id, company.id),
    )
    assert response.status_code == 403


async def test_remove_member_foreign_company(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    other = _company(f"Remove Foreign {uuid4().hex[:6]}")
    other_owner = _user(f"remove-owner-{uuid4().hex[:6]}@example.com")
    other_owner_membership = _membership(other_owner, other, "OWNER")
    db_session.add_all([other, other_owner, other_owner_membership])
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/companies/{other.id}/members/{other_owner_membership.id}",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code == 403
    remaining = await db_session.execute(
        select(CompanyMember).where(CompanyMember.company_id == other.id)
    )
    assert [str(m.id) for m in remaining.scalars().all()] == [
        str(other_owner_membership.id)
    ]


async def test_remove_last_owner_rejected(client, db_session):
    company = _company(f"Remove Last {uuid4().hex[:6]}")
    owner = _user(f"remove-last-{uuid4().hex[:6]}@example.com")
    membership = _membership(owner, company, "OWNER")
    db_session.add_all([company, owner, membership])
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/companies/{company.id}/members/{membership.id}",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code in (403, 409)


async def test_remove_owner_by_admin_forbidden(client, db_session):
    company, _, admin, _, owner_membership, _, _ = await _administration_fixture(
        db_session
    )

    response = await client.delete(
        f"/api/v1/companies/{company.id}/members/{owner_membership.id}",
        headers=_headers(admin.id, company.id),
    )
    assert response.status_code == 403


async def test_remove_nonexistent_member_404(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)

    response = await client.delete(
        f"/api/v1/companies/{company.id}/members/{uuid4()}",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code in (403, 404)


async def test_revoke_invitation(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "revoke@example.com", "role": "VIEWER"},
        headers=_headers(owner.id, company.id),
    )
    assert invite.status_code == 200
    invitation_id = invite.json()["id"]

    response = await client.delete(
        f"/api/v1/companies/{company.id}/invitations/{invitation_id}",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code == 200

    row = await db_session.execute(
        select(Invitation).where(Invitation.id == invitation_id)
    )
    assert row.scalar_one().status == "revoked"


async def test_revoke_invitation_forbidden_role(client, db_session):
    company, _, admin, member, _, _, _ = await _administration_fixture(db_session)
    invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "revoke2@example.com", "role": "VIEWER"},
        headers=_headers(admin.id, company.id),
    )
    assert invite.status_code == 200
    invitation_id = invite.json()["id"]

    response = await client.delete(
        f"/api/v1/companies/{company.id}/invitations/{invitation_id}",
        headers=_headers(member.id, company.id),
    )
    assert response.status_code == 403


async def test_revoke_invitation_foreign_company(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    other = _company(f"Revoke Foreign {uuid4().hex[:6]}")
    other_owner = _user(f"revoke-owner-{uuid4().hex[:6]}@example.com")
    db_session.add_all([other, other_owner, _membership(other_owner, other, "OWNER")])
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/companies/{other.id}/invitations/{uuid4()}",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code == 403
    rows = await db_session.execute(
        select(Invitation).where(Invitation.company_id == other.id)
    )
    assert rows.scalars().all() == []


async def test_revoke_invitation_nonexistent(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)

    response = await client.delete(
        f"/api/v1/companies/{company.id}/invitations/{uuid4()}",
        headers=_headers(owner.id, company.id),
    )
    assert response.status_code in (403, 404)


async def test_revoke_invitation_already_revoked(client, db_session):
    company, owner, _, _, _, _, _ = await _administration_fixture(db_session)
    invite = await client.post(
        f"/api/v1/companies/{company.id}/invitations",
        json={"email": "double-revoke@example.com", "role": "VIEWER"},
        headers=_headers(owner.id, company.id),
    )
    invitation_id = invite.json()["id"]
    first = await client.delete(
        f"/api/v1/companies/{company.id}/invitations/{invitation_id}",
        headers=_headers(owner.id, company.id),
    )
    second = await client.delete(
        f"/api/v1/companies/{company.id}/invitations/{invitation_id}",
        headers=_headers(owner.id, company.id),
    )
    assert first.status_code == 200
    assert second.status_code == 400
