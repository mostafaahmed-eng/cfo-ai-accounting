from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.company import CompanyMember
from app.models.user import User
from app.services.auth import decode_token

security = HTTPBearer()
settings = get_settings()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None or getattr(user.status, "value", user.status) != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def resolve_company_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    selected_company_id: str | None = None,
) -> CompanyMember:
    selected_uuid = None
    if selected_company_id:
        try:
            selected_uuid = UUID(selected_company_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid company selection",
            )

    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.user_id == user.id,
            CompanyMember.status == "active",
            *(
                [CompanyMember.company_id == selected_uuid]
                if selected_uuid is not None
                else []
            ),
        )
    )
    memberships = result.scalars().all()

    if selected_uuid is not None:
        if not memberships:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company selection is not available",
            )
        return memberships[0]

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no company",
        )

    if len(memberships) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Explicit company selection required",
        )

    return memberships[0]


async def get_current_company_membership(
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyMember:
    return await resolve_company_membership(
        user=user,
        db=db,
        selected_company_id=x_company_id,
    )


async def get_current_company_id(
    membership: CompanyMember = Depends(get_current_company_membership),
) -> UUID:
    return membership.company_id
