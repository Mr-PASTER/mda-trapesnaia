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
