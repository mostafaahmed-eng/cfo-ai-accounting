from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import CompanyMember

ADMIN_ROLES = {"OWNER", "ADMIN"}


def require_company_administrator(
    membership: CompanyMember,
    company_id: UUID,
) -> None:
    if (
        membership.company_id != company_id
        or membership.status != "active"
        or membership.role not in ADMIN_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company administrator access required",
        )


async def lock_active_owners(
    db: AsyncSession,
    company_id: UUID,
) -> list[CompanyMember]:
    result = await db.execute(
        select(CompanyMember)
        .where(
            CompanyMember.company_id == company_id,
            CompanyMember.role == "OWNER",
            CompanyMember.status == "active",
        )
        .order_by(CompanyMember.id)
        .with_for_update()
    )
    return list(result.scalars().all())


async def authorize_member_update(
    db: AsyncSession,
    *,
    actor: CompanyMember,
    target: CompanyMember,
    new_role: str | None,
    new_status: str | None,
) -> CompanyMember:
    require_company_administrator(actor, target.company_id)

    active_owners = await lock_active_owners(db, target.company_id)
    actor = (
        await db.execute(
            select(CompanyMember)
            .where(
                CompanyMember.id == actor.id,
                CompanyMember.company_id == target.company_id,
            )
            .with_for_update()
        )
    ).scalar_one()
    target = (
        await db.execute(
            select(CompanyMember)
            .where(
                CompanyMember.id == target.id,
                CompanyMember.company_id == target.company_id,
            )
            .with_for_update()
        )
    ).scalar_one()
    require_company_administrator(actor, target.company_id)

    if (target.role == "OWNER" or new_role == "OWNER") and actor.role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner may change owner status",
        )

    removes_active_owner = (
        target.role == "OWNER"
        and target.status == "active"
        and (new_role not in (None, "OWNER") or new_status == "disabled")
    )
    if removes_active_owner:
        if len(active_owners) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active owner cannot be changed",
            )
    return target


async def authorize_member_removal(
    db: AsyncSession,
    *,
    actor: CompanyMember,
    target: CompanyMember,
) -> CompanyMember:
    """Authorize and locate a member being removed (hard delete / uninvited).

    Follows the same rules as updates:
    - Only a company administrator may remove members.
    - Only an OWNER may remove another OWNER.
    - The last active owner can never be removed (409).
    """
    require_company_administrator(actor, target.company_id)

    active_owners = await lock_active_owners(db, target.company_id)
    actor = (
        await db.execute(
            select(CompanyMember)
            .where(
                CompanyMember.id == actor.id,
                CompanyMember.company_id == target.company_id,
            )
            .with_for_update()
        )
    ).scalar_one()
    target = (
        await db.execute(
            select(CompanyMember)
            .where(
                CompanyMember.id == target.id,
                CompanyMember.company_id == target.company_id,
            )
            .with_for_update()
        )
    ).scalar_one()
    require_company_administrator(actor, target.company_id)

    if target.role == "OWNER" and actor.role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner may remove an owner",
        )

    if target.role == "OWNER" and target.status == "active":
        if len(active_owners) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active owner cannot be changed",
            )
    return target
