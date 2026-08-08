from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    RefreshRequest,
    RefreshResponse,
    UserResponse,
    UserUpdate,
)
from app.services.audit import create_audit_log, create_audit_log_independent
from app.services.auth import create_access_token, decode_token
from app.services.refresh_tokens import (
    issue_refresh_token,
    revoke_all_user_tokens,
    rotate_refresh_token,
)

router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    if not user or not user.password_hash:
        # Failure audit is persisted in its own committed transaction: the
        # HTTPException below would otherwise roll back the request session.
        await create_audit_log_independent(
            company_id=None,
            user_id=None,
            actor_type="user",
            action="auth.login_failed",
            entity_type="user",
            entity_id=data.email,
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not verify_password(data.password, user.password_hash):
        await create_audit_log_independent(
            company_id=None,
            user_id=str(user.id),
            actor_type="user",
            action="auth.login_failed",
            entity_type="user",
            entity_id=str(user.id),
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if getattr(user.status, "value", user.status) != "active":
        await create_audit_log_independent(
            company_id=None,
            user_id=str(user.id),
            actor_type="user",
            action="auth.login_disabled",
            entity_type="user",
            entity_id=str(user.id),
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
        )

    access_token = create_access_token(str(user.id), ver=user.token_version)
    refresh_token = await issue_refresh_token(db, user, ip_address=ip, user_agent=ua)

    await create_audit_log(
        db=db,
        company_id=None,
        user_id=str(user.id),
        actor_type="user",
        action="auth.login_success",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=ip,
        user_agent=ua,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    data: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or getattr(user.status, "value", user.status) != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    if payload.get("ver") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalidated",
        )

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    new_refresh = await rotate_refresh_token(
        db,
        token=data.refresh_token,
        jti=str(jti),
        user=user,
        ip_address=ip,
        user_agent=ua,
    )
    if new_refresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked; please sign in again",
        )

    access_token = create_access_token(str(user.id), ver=user.token_version)
    return RefreshResponse(
        access_token=access_token,
        refresh_token=new_refresh,
    )


@router.post("/logout")
async def logout(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await revoke_all_user_tokens(db, user.id)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.name is not None:
        user.name = data.name
    if data.language is not None:
        user.language = data.language
    if data.timezone is not None:
        user.timezone = data.timezone
    await db.flush()
    return UserResponse.model_validate(user)


@router.post("/change-password")
async def change_password(
    data: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    if not user.password_hash or not verify_password(
        data.current_password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = hash_password(data.new_password)
    user.token_version = (user.token_version or 0) + 1
    await revoke_all_user_tokens(db, user.id)
    await db.flush()

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await create_audit_log(
        db=db,
        company_id=None,
        user_id=str(user.id),
        actor_type="user",
        action="auth.password_changed",
        entity_type="user",
        entity_id=str(user.id),
        after_data={"token_version": user.token_version},
        ip_address=ip,
        user_agent=ua,
    )
    return {"message": "Password changed successfully"}
