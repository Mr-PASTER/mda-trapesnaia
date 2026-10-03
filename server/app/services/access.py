import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserHall, UserRole


class AccessDenied(Exception):
    pass


async def hall_ids_of(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    result = await db.execute(select(UserHall.hall_id).where(UserHall.user_id == user_id))
    return set(result.scalars().all())


async def ensure_can_edit_user(db: AsyncSession, *, actor: User, target: User) -> None:
    if actor.id == target.id:
        return
    if actor.role == UserRole.admin:
        if await hall_ids_of(db, actor.id) & await hall_ids_of(db, target.id):
            return
    raise AccessDenied()
