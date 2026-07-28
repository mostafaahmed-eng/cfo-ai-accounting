import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.telegram import TelegramConnection, TelegramPairing
from app.services.audit import create_audit_log

PAIRING_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
settings = get_settings()


@dataclass
class PairingCreation:
    pairing: TelegramPairing
    code: str


@dataclass
class PairingResult:
    connection: TelegramConnection | None
    reason: str

    @property
    def succeeded(self) -> bool:
        return self.connection is not None


def hash_pairing_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def is_well_formed_pairing_code(code: str) -> bool:
    return bool(PAIRING_CODE_PATTERN.fullmatch(code))


async def create_pairing(
    db: AsyncSession,
    connection: TelegramConnection,
    company_id,
    user_id,
) -> PairingCreation:
    now = datetime.now(UTC).replace(tzinfo=None)

    old_pairings = await db.execute(
        select(TelegramPairing)
        .where(
            TelegramPairing.connection_id == connection.id,
            TelegramPairing.status == "pending",
        )
        .with_for_update()
    )
    for old_pairing in old_pairings.scalars().all():
        old_pairing.status = "revoked"

    code = secrets.token_urlsafe(32)
    pairing = TelegramPairing(
        id=uuid4(),
        connection_id=connection.id,
        company_id=company_id,
        secret_hash=hash_pairing_code(code),
        status="pending",
        expires_at=now + timedelta(minutes=settings.TELEGRAM_PAIRING_TTL_MINUTES),
        created_by=user_id,
        failed_attempts=0,
    )
    db.add(pairing)
    await db.flush()

    await create_audit_log(
        db=db,
        company_id=str(company_id),
        user_id=str(user_id),
        actor_type="user",
        action="telegram.pairing_created",
        entity_type="telegram_pairing",
        entity_id=str(pairing.id),
        after_data={
            "connection_id": str(connection.id),
            "expires_at": pairing.expires_at.isoformat(),
        },
    )
    return PairingCreation(pairing=pairing, code=code)


async def _audit_pairing_failure(
    db: AsyncSession,
    *,
    pairing: TelegramPairing | None,
    chat_id: int,
    reason: str,
) -> None:
    await create_audit_log(
        db=db,
        company_id=str(pairing.company_id) if pairing else None,
        user_id=None,
        actor_type="telegram",
        action="telegram.pairing_failed",
        entity_type="telegram_pairing",
        entity_id=str(pairing.id) if pairing else "unknown",
        after_data={"reason": reason, "chat_id": chat_id},
    )


async def consume_pairing(
    db: AsyncSession,
    *,
    code: str,
    chat_id: int,
) -> PairingResult:
    if not is_well_formed_pairing_code(code):
        await _audit_pairing_failure(
            db, pairing=None, chat_id=chat_id, reason="malformed"
        )
        return PairingResult(connection=None, reason="invalid")

    pairing_result = await db.execute(
        select(TelegramPairing)
        .where(TelegramPairing.secret_hash == hash_pairing_code(code))
        .with_for_update()
    )
    pairing = pairing_result.scalar_one_or_none()
    if pairing is None:
        await _audit_pairing_failure(
            db, pairing=None, chat_id=chat_id, reason="unknown"
        )
        return PairingResult(connection=None, reason="invalid")

    now = datetime.now(UTC).replace(tzinfo=None)
    if pairing.status != "pending":
        pairing.failed_attempts += 1
        pairing.last_failed_at = now
        await _audit_pairing_failure(
            db, pairing=pairing, chat_id=chat_id, reason="replayed"
        )
        return PairingResult(connection=None, reason="invalid")

    if pairing.expires_at <= now:
        pairing.status = "expired"
        pairing.failed_attempts += 1
        pairing.last_failed_at = now
        await _audit_pairing_failure(
            db, pairing=pairing, chat_id=chat_id, reason="expired"
        )
        return PairingResult(connection=None, reason="invalid")

    connection_result = await db.execute(
        select(TelegramConnection)
        .where(
            TelegramConnection.id == pairing.connection_id,
            TelegramConnection.company_id == pairing.company_id,
        )
        .with_for_update()
    )
    connection = connection_result.scalar_one_or_none()
    if connection is None or connection.status != "pending_chat_id":
        pairing.failed_attempts += 1
        pairing.last_failed_at = now
        await _audit_pairing_failure(
            db, pairing=pairing, chat_id=chat_id, reason="connection_unavailable"
        )
        return PairingResult(connection=None, reason="invalid")

    existing_chat = await db.execute(
        select(TelegramConnection.id).where(
            TelegramConnection.telegram_chat_id == chat_id,
            TelegramConnection.status == "active",
        )
    )
    if existing_chat.scalar_one_or_none() is not None:
        pairing.failed_attempts += 1
        pairing.last_failed_at = now
        await _audit_pairing_failure(
            db, pairing=pairing, chat_id=chat_id, reason="chat_already_connected"
        )
        return PairingResult(connection=None, reason="invalid")

    connection.telegram_chat_id = chat_id
    connection.status = "active"
    pairing.status = "consumed"
    pairing.consumed_at = now
    pairing.consumed_by_chat_id = chat_id
    await db.flush()

    await create_audit_log(
        db=db,
        company_id=str(pairing.company_id),
        user_id=None,
        actor_type="telegram",
        action="telegram.pairing_succeeded",
        entity_type="telegram_pairing",
        entity_id=str(pairing.id),
        after_data={
            "connection_id": str(connection.id),
            "chat_id": chat_id,
        },
    )
    return PairingResult(connection=connection, reason="paired")
