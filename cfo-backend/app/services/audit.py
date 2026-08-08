from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.audit_log import AuditLog


async def create_audit_log(
    db: AsyncSession,
    company_id: str | None,
    user_id: str | None,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before_data: dict | None = None,
    after_data: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    log = AuditLog(
        id=uuid4(),
        company_id=company_id,
        user_id=user_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=before_data,
        after_data=after_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    await db.flush()
    return log


async def create_audit_log_independent(
    company_id: str | None,
    user_id: str | None,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before_data: dict | None = None,
    after_data: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Persist an audit row in its own committed transaction.

    Used for security-relevant events (e.g. failed logins) that are written
    right before the request handler raises. Those raise paths otherwise cause
    the request session to roll back, silently discarding the audit row.
    """
    import logging

    logger = logging.getLogger(__name__)
    try:
        async with async_session() as session:
            await create_audit_log(
                session,
                company_id,
                user_id,
                actor_type,
                action,
                entity_type,
                entity_id,
                before_data,
                after_data,
                ip_address,
                user_agent,
            )
            await session.commit()
    except Exception:
        # The audit write must never change the auth outcome or crash the
        # request; log and continue with the original auth response.
        logger.warning("Failed to persist independent audit log", exc_info=True)
