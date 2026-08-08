from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.account import Account
from app.models.user import User
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    ImportTemplateRequest,
)
from app.schemas.pagination import PageParams, get_page_params

router = APIRouter()


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
):
    filters = (Account.company_id == company_id,)
    total = await db.scalar(select(func.count()).select_from(Account).where(*filters))
    result = await db.execute(
        select(Account)
        .where(*filters)
        .order_by(Account.code)
        .offset(page.offset)
        .limit(page.limit)
    )
    response.headers["X-Total-Count"] = str(total)
    return [AccountResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Account).where(
            Account.id == account_id, Account.company_id == company_id
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountResponse.model_validate(account)


@router.post("", response_model=AccountResponse)
async def create_account(
    data: AccountCreate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    account = Account(
        id=uuid4(),
        company_id=company_id,
        code=data.code,
        name_en=data.name_en,
        name_ar=data.name_ar,
        type=data.type.value,
        subtype=data.subtype,
        currency=data.currency,
        parent_account_id=data.parent_account_id,
        is_payment_account=data.is_payment_account,
        is_active=True,
        is_system=False,
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
    result = await db.execute(
        select(Account).where(
            Account.id == account_id, Account.company_id == company_id
        )
    )
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
    return {
        "format": data.format,
        "template": "code,name_en,name_ar,type,subtype,currency,parent_code,is_payment_account",
    }
