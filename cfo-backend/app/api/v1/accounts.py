from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from app.database import get_db
from app.models.account import Account
from app.models.user import User
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse, ImportTemplateRequest
from app.dependencies import get_current_user, get_current_company_id

router = APIRouter()


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Account).where(Account.company_id == company_id).order_by(Account.code))
    return [AccountResponse.model_validate(a) for a in result.scalars().all()]


@router.post("", response_model=AccountResponse)
async def create_account(
    data: AccountCreate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    account = Account(
        id=uuid4(), company_id=company_id, code=data.code,
        name_en=data.name_en, name_ar=data.name_ar, type=data.type.value,
        subtype=data.subtype, currency=data.currency, parent_account_id=data.parent_account_id,
        is_payment_account=data.is_payment_account, is_active=True, is_system=False,
    )
    db.add(account)
    await db.flush()
    return AccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    data: AccountUpdate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Account).where(Account.id == account_id, Account.company_id == company_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await db.flush()
    return AccountResponse.model_validate(account)


@router.post("/import-template")
async def import_template(
    data: ImportTemplateRequest,
    user: User = Depends(get_current_user),
):
    return {"format": data.format, "template": "code,name_en,name_ar,type,subtype,currency,parent_code,is_payment_account"}
