import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MealType


async def get(db: AsyncSession, meal_type_id: uuid.UUID) -> MealType | None:
    return await db.get(MealType, meal_type_id)


async def get_by_name(db: AsyncSession, name: str) -> MealType | None:
    result = await db.execute(select(MealType).where(MealType.name == name))
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession, *, only_active: bool) -> list[MealType]:
    stmt = select(MealType).order_by(MealType.sort_order, MealType.name)
    if only_active:
        stmt = stmt.where(MealType.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def count_active(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(MealType).where(MealType.is_active.is_(True))
    )
    return int(result.scalar_one())


async def add(db: AsyncSession, meal_type: MealType) -> MealType:
    db.add(meal_type)
    await db.flush()
    return meal_type
