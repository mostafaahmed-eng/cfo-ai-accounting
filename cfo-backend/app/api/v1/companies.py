from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
import secrets
import hashlib
from app.database import get_db
from app.models.user import User
from app.models.company import Company, CompanyMember
from app.models.account import Account
from app.models.invitation import Invitation
from app.schemas.company import (
    CompanyCreate,
    CompanyMembershipResponse,
    CompanyResponse,
    InvitationCreate,
    InvitationResponse,
    MemberUpdate,
    MemberResponse,
)
from app.dependencies import get_current_company_membership, get_current_user
from app.enums import UserRole, AccountType
from app.services.audit import create_audit_log
from app.services.company_authorization import (
    authorize_member_update,
    require_company_administrator,
)

router = APIRouter()

DEFAULT_ACCOUNTS = [
    {
        "code": "1000",
        "name_en": "Cash",
        "type": AccountType.asset,
        "subtype": "cash",
        "is_payment_account": True,
        "is_system": True,
    },
    {
        "code": "1100",
        "name_en": "Bank",
        "type": AccountType.asset,
        "subtype": "bank",
        "is_payment_account": True,
        "is_system": True,
    },
    {
        "code": "1200",
        "name_en": "Accounts Receivable",
        "type": AccountType.asset,
        "subtype": "receivable",
        "is_system": True,
    },
    {
        "code": "2000",
        "name_en": "Accounts Payable",
        "type": AccountType.liability,
        "subtype": "payable",
        "is_system": True,
    },
    {
        "code": "4000",
        "name_en": "Sales Revenue",
        "type": AccountType.revenue,
        "subtype": "sales",
        "is_system": True,
    },
    {
        "code": "5000",
        "name_en": "Hosting Expenses",
        "type": AccountType.expense,
        "subtype": "hosting",
        "is_system": True,
    },
    {
        "code": "5100",
        "name_en": "Software Expenses",
        "type": AccountType.expense,
        "subtype": "software",
        "is_system": True,
    },
    {
        "code": "5200",
        "name_en": "Marketing Expenses",
        "type": AccountType.expense,
        "subtype": "marketing",
        "is_system": True,
    },
    {
        "code": "5300",
        "name_en": "Payroll Expenses",
        "type": AccountType.expense,
        "subtype": "payroll",
        "is_system": True,
    },
]


@router.post("", response_model=CompanyResponse)
async def create_company(
    data: CompanyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    company = Company(
        id=uuid4(),
        name=data.name,
        legal_name=data.legal_name,
        country_code=data.country_code,
        base_currency=data.base_currency,
        fiscal_year_start=data.fiscal_year_start,
        timezone=data.timezone,
        tax_number=data.tax_number,
    )
    db.add(company)

    for acct in DEFAULT_ACCOUNTS:
        db.add(
            Account(
                id=uuid4(),
                company_id=str(company.id),
                code=acct["code"],
                name_en=acct["name_en"],
                type=acct["type"].value,
                subtype=acct["subtype"],
                is_payment_account=acct.get("is_payment_account", False),
                is_system=acct.get("is_system", False),
                is_active=True,
            )
        )

    member = CompanyMember(
        id=uuid4(),
        company_id=str(company.id),
        user_id=str(user.id),
        role=UserRole.OWNER.value,
        status="active",
        joined_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db.add(member)
    await db.flush()

    await create_audit_log(
        db=db,
        company_id=str(company.id),
        user_id=str(user.id),
        actor_type="user",
        action="company.created",
        entity_type="company",
        entity_id=str(company.id),
        after_data={"name": company.name},
    )

    return CompanyResponse.model_validate(company)


@router.get("/memberships", response_model=list[CompanyMembershipResponse])
async def list_company_memberships(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CompanyMember, Company)
        .join(Company, Company.id == CompanyMember.company_id)
        .where(
            CompanyMember.user_id == user.id,
            CompanyMember.status == "active",
        )
        .order_by(Company.name, Company.id)
    )
    return [
        CompanyMembershipResponse(
            membership_id=membership.id,
            company_id=company.id,
            company_name=company.name,
            role=membership.role,
        )
        for membership, company in result.all()
    ]


@router.post("/{company_id}/invitations", response_model=InvitationResponse)
async def invite_member(
    company_id: UUID,
    data: InvitationCreate,
    user: User = Depends(get_current_user),
    actor: CompanyMember = Depends(get_current_company_membership),
    db: AsyncSession = Depends(get_db),
):
    require_company_administrator(actor, company_id)
    if data.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Owner invitations are not supported",
        )

    existing = await db.execute(
        select(Invitation).where(
            Invitation.company_id == company_id,
            Invitation.email == data.email,
            Invitation.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pending invitation already exists for this email",
        )

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    invitation = Invitation(
        id=uuid4(),
        company_id=company_id,
        email=data.email,
        role=data.role.value,
        token_hash=token_hash,
        invited_by=user.id,
        status="pending",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()

    await create_audit_log(
        db=db,
        company_id=str(company_id),
        user_id=str(user.id),
        actor_type="user",
        action="invitation.created",
        entity_type="invitation",
        entity_id=str(invitation.id),
        after_data={"email": data.email, "role": data.role.value},
    )

    return InvitationResponse(
        id=invitation.id,
        company_id=company_id,
        email=invitation.email,
        role=data.role,
        status="pending",
        joined_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


@router.patch("/{company_id}/members/{member_id}", response_model=MemberResponse)
async def update_member(
    company_id: UUID,
    member_id: UUID,
    data: MemberUpdate,
    user: User = Depends(get_current_user),
    actor: CompanyMember = Depends(get_current_company_membership),
    db: AsyncSession = Depends(get_db),
):
    require_company_administrator(actor, company_id)
    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.id == member_id,
            CompanyMember.company_id == company_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    new_role = data.role.value if data.role is not None else None
    new_status = data.status.value if data.status is not None else None
    member = await authorize_member_update(
        db,
        actor=actor,
        target=member,
        new_role=new_role,
        new_status=new_status,
    )

    before = {"role": member.role, "status": member.status}
    if data.role is not None:
        member.role = new_role
    if data.status is not None:
        member.status = new_status
    await db.flush()

    after = {"role": member.role, "status": member.status}
    if before != after:
        await create_audit_log(
            db=db,
            company_id=str(company_id),
            user_id=str(user.id),
            actor_type="user",
            action="membership.updated",
            entity_type="company_member",
            entity_id=str(member.id),
            before_data=before,
            after_data=after,
        )
    return MemberResponse.model_validate(member)
