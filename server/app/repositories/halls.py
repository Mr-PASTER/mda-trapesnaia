import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall


async def get(db: AsyncSession, hall_id: uuid.UUID) -> Hall | None:
    return await db.get(Hall, hall_id)


async def get_by_name(db: AsyncSession, name: str) -> Hall | None:
    result = await db.execute(select(Hall).where(Hall.name == name))
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession, *, only_active: bool) -> list[Hall]:
    stmt = select(Hall).order_by(Hall.name)
    if only_active:
        stmt = stmt.where(Hall.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def add(db: AsyncSession, hall: Hall) -> Hall:
    db.add(hall)
    await db.flush()
    return hall
