from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def create(
    db: AsyncSession,
    *,
    user_id,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict | None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(log)
    await db.flush()
    return log


async def list_logs(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    user_id=None,
    limit: int = 1000,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.created_at <= until)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return list((await db.execute(stmt)).scalars().all())


async def delete_older_than(db: AsyncSession, cutoff: datetime) -> int:
    result = await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.flush()
    return int(result.rowcount or 0)
