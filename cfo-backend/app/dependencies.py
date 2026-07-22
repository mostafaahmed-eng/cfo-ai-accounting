from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from jose import jwt, JWTError
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.company import CompanyMember

security = HTTPBearer()
settings = get_settings()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
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
    if user is None or user.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


# A single user can belong to multiple companies (e.g. an accountant serving
# several clients, or an employee with side projects).  The old implementation
# used ``scalar_one_or_none()`` which raised ``MultipleResultsFound`` the
# moment a user had two active memberships.  We now fetch all active
# memberships and pick the best one:
#   1. Prefer the membership whose role is OWNER (highest privilege).
#   2. If there is no OWNER, return the first active membership.
#   3. If the user has no active membership at all, return 403.
async def get_current_company_id(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    result = await db.execute(
        select(CompanyMember).where(
            CompanyMember.user_id == user.id,
            CompanyMember.status == "active",
        )
    )
    memberships = result.scalars().all()

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no company",
        )

    # Prefer OWNER so the default company is the one the user owns.
    for m in memberships:
        if m.role == "OWNER":
            return m.company_id

    # No OWNER found — fall back to the first active membership.
    return memberships[0].company_id
