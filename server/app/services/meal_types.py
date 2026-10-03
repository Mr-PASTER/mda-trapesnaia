import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MealType
from app.repositories import meal_types as repo
from app.services import audit


class MealTypeAlreadyExists(Exception):
    pass


class LastMealType(Exception):
    pass


async def create_meal_type(
    db: AsyncSession, *, actor_id: uuid.UUID, name: str, sort_order: int = 0
) -> MealType:
    name = name.strip()
    if await repo.get_by_name(db, name) is not None:
        raise MealTypeAlreadyExists(name)
    mt = await repo.add(db, MealType(name=name, sort_order=sort_order))
    await audit.record(
        db, actor_id=actor_id, action="create", entity_type="meal_type",
        entity_id=str(mt.id), details={"name": name},
    )
    return mt


async def list_meal_types(db: AsyncSession, *, only_active: bool = True) -> list[MealType]:
    return await repo.list_all(db, only_active=only_active)


async def update_meal_type(
    db: AsyncSession, *, actor_id: uuid.UUID, meal_type_id: uuid.UUID,
    name: str | None = None, sort_order: int | None = None, is_active: bool | None = None,
) -> MealType:
    mt = await repo.get(db, meal_type_id)
    if mt is None:
        raise LookupError("meal_type_not_found")
    if name is not None:
        name = name.strip()
        existing = await repo.get_by_name(db, name)
        if existing is not None and existing.id != mt.id:
            raise MealTypeAlreadyExists(name)
        mt.name = name
    if sort_order is not None:
        mt.sort_order = sort_order
    if is_active is False and mt.is_active and await repo.count_active(db) <= 1:
        raise LastMealType()
    if is_active is not None:
        mt.is_active = is_active
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="meal_type",
        entity_id=str(mt.id), details={"name": mt.name, "is_active": mt.is_active},
    )
    return mt


async def deactivate_meal_type(
    db: AsyncSession, *, actor_id: uuid.UUID, meal_type_id: uuid.UUID
) -> None:
    mt = await repo.get(db, meal_type_id)
    if mt is None:
        raise LookupError("meal_type_not_found")
    if mt.is_active and await repo.count_active(db) <= 1:
        raise LastMealType()
    mt.is_active = False
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="delete", entity_type="meal_type",
        entity_id=str(mt.id), details={"soft": True},
    )
