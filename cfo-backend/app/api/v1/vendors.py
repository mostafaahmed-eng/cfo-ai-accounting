from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from app.database import get_db
from app.models.vendor import Vendor, VendorAlias
from app.models.user import User
from app.schemas.vendor import (
    VendorCreate,
    VendorUpdate,
    VendorResponse,
    AliasCreate,
    AliasResponse,
)
from app.dependencies import get_current_user, get_current_company_id

router = APIRouter()


def normalize_name(name: str) -> str:
    return " ".join(name.lower().strip().split())


@router.get("", response_model=list[VendorResponse])
async def list_vendors(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vendor)
        .where(Vendor.company_id == company_id, Vendor.is_active)
        .order_by(Vendor.name)
    )
    return [VendorResponse.model_validate(v) for v in result.scalars().all()]


@router.post("", response_model=VendorResponse)
async def create_vendor(
    data: VendorCreate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    vendor = Vendor(
        id=uuid4(),
        company_id=company_id,
        name=data.name,
        normalized_name=normalize_name(data.name),
        email=data.email,
        phone=data.phone,
        tax_number=data.tax_number,
        country_code=data.country_code,
        default_expense_account=data.default_expense_account,
        default_currency=data.default_currency,
        is_active=True,
    )
    db.add(vendor)
    await db.flush()
    return VendorResponse.model_validate(vendor)


@router.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: str,
    data: VendorUpdate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.company_id == company_id)
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "name" and value:
            vendor.normalized_name = normalize_name(value)
        setattr(vendor, field, value)
    await db.flush()
    return VendorResponse.model_validate(vendor)


@router.post("/{vendor_id}/aliases", response_model=AliasResponse)
async def add_alias(
    vendor_id: str,
    data: AliasCreate,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.company_id == company_id)
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    alias = VendorAlias(
        id=uuid4(),
        vendor_id=vendor_id,
        alias=data.alias,
        normalized_alias=normalize_name(data.alias),
    )
    db.add(alias)
    await db.flush()
    return AliasResponse.model_validate(alias)


@router.post("/{vendor_id}/deactivate", response_model=VendorResponse)
async def deactivate_vendor(
    vendor_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.company_id == company_id)
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.is_active = False
    await db.flush()
    return VendorResponse.model_validate(vendor)
