import uuid
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings
from app.repositories import settings as repo
from app.services import audit


async def get_settings(db: AsyncSession) -> AppSettings:
    return await repo.ensure(db)


async def update_settings(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    generation_days: int | None = None,
    deadline_offset_days: int | None = None,
    deadline_time: time | None = None,
) -> AppSettings:
    if generation_days is not None and generation_days < 1:
        raise ValueError("generation_days must be >= 1")
    if deadline_offset_days is not None and deadline_offset_days < 0:
        raise ValueError("deadline_offset_days must be >= 0")

    row = await repo.ensure(db)
    if generation_days is not None:
        row.generation_days = generation_days
    if deadline_offset_days is not None:
        row.deadline_offset_days = deadline_offset_days
    if deadline_time is not None:
        row.deadline_time = deadline_time
    await db.flush()
    await audit.record(
        db,
        actor_id=actor_id,
        action="update",
        entity_type="settings",
        entity_id="1",
        details={
            "generation_days": row.generation_days,
            "deadline_offset_days": row.deadline_offset_days,
            "deadline_time": row.deadline_time.isoformat(),
        },
    )
    return row
