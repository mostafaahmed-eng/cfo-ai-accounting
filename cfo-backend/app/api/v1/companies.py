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
    CompanyResponse,
    InvitationCreate,
    InvitationResponse,
    MemberUpdate,
    MemberResponse,
)
from app.dependencies import get_current_user, get_current_company_id
from app.enums import UserRole, AccountType
from app.services.audit import create_audit_log

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


@router.post("/{company_id}/invitations", response_model=InvitationResponse)
async def invite_member(
    company_id: str,
    data: InvitationCreate,
    user: User = Depends(get_current_user),
    company_id_dep: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    if str(company_id) != str(company_id_dep):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your company"
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
        invited_by=str(user.id),
        status="pending",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()

    await create_audit_log(
        db=db,
        company_id=company_id,
        user_id=str(user.id),
        actor_type="user",
        action="invitation.created",
        entity_type="invitation",
        entity_id=str(invitation.id),
        after_data={"email": data.email, "role": data.role.value},
    )

    return InvitationResponse(
        id=invitation.id,
        company_id=UUID(company_id) if isinstance(company_id, str) else company_id,
        email=invitation.email,
        role=data.role,
        status="pending",
        joined_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


@router.patch("/{company_id}/members/{member_id}", response_model=MemberResponse)
async def update_member(
    company_id: str,
    member_id: str,
    data: MemberUpdate,
    user: User = Depends(get_current_user),
    company_id_dep: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    if str(company_id) != str(company_id_dep):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your company"
        )
    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.id == member_id, CompanyMember.company_id == company_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if data.role is not None:
        member.role = data.role.value
    if data.status is not None:
        member.status = data.status.value
    await db.flush()
    return MemberResponse.model_validate(member)
