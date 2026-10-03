import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import audit as audit_repo


async def record(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    await audit_repo.create(
        db,
        user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
