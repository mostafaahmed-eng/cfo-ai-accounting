from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company_id, get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.pagination import PageParams, get_page_params

router = APIRouter()


@router.get("")
async def list_audit_logs(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    page: PageParams = Depends(get_page_params),
):
    filters = (AuditLog.company_id == company_id,)
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters))
    result = await db.execute(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
    )
    logs = result.scalars().all()
    response.headers["X-Total-Count"] = str(total)
    return [
        {
            "id": str(log.id),
            "actor_type": log.actor_type,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
