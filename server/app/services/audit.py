import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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


async def list_logs(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    user_id=None,
    limit: int = 1000,
) -> list:
    return await audit_repo.list_logs(
        db, since=since, until=until, user_id=user_id, limit=limit
    )


def today_reset_point(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(settings.timezone)
    now = now or datetime.now(tz)
    return datetime.combine(now.date(), datetime.min.time(), tzinfo=tz)


async def cleanup_older_than(db: AsyncSession, cutoff: datetime) -> int:
    return await audit_repo.delete_older_than(db, cutoff)
