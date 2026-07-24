import hashlib
import re
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inbox_item import InboxItem


@dataclass
class IntakeCreation:
    item: InboxItem
    created: bool


def normalized_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def create_text_inbox(
    db: AsyncSession,
    *,
    company_id,
    text: str,
    language: str,
    source: str,
    submitted_by=None,
    idempotency_key: str | None = None,
    source_reference: str | None = None,
) -> IntakeCreation:
    content_hash = normalized_text_hash(text)
    advisory_key = int(content_hash[:15], 16)
    await db.execute(select(func.pg_advisory_xact_lock(advisory_key)))

    if idempotency_key:
        existing = await db.execute(
            select(InboxItem).where(
                InboxItem.company_id == company_id,
                InboxItem.source == source,
                InboxItem.idempotency_key == idempotency_key,
            )
        )
    else:
        existing = await db.execute(
            select(InboxItem)
            .where(
                InboxItem.company_id == company_id,
                InboxItem.content_hash == content_hash,
                InboxItem.content_type == "text",
            )
            .order_by(InboxItem.created_at.desc())
        )
    existing_item = existing.scalars().first()
    if existing_item:
        return IntakeCreation(item=existing_item, created=False)

    item = InboxItem(
        id=uuid4(),
        company_id=company_id,
        source=source,
        source_reference=source_reference,
        content_type="text",
        original_text=text,
        detected_language=language,
        status="queued",
        submitted_by=submitted_by,
        idempotency_key=idempotency_key,
        content_hash=content_hash,
        duplicate_status="unique",
    )
    db.add(item)
    await db.flush()
    return IntakeCreation(item=item, created=True)
