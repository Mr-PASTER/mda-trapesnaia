import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall
from app.repositories import halls as halls_repo
from app.services import audit


class HallAlreadyExists(Exception):
    pass


async def create_hall(db: AsyncSession, *, actor_id: uuid.UUID, name: str) -> Hall:
    name = name.strip()
    if await halls_repo.get_by_name(db, name) is not None:
        raise HallAlreadyExists(name)
    hall = await halls_repo.add(db, Hall(name=name))
    await audit.record(
        db,
        actor_id=actor_id,
        action="create",
        entity_type="hall",
        entity_id=str(hall.id),
        details={"name": name},
    )
    return hall


async def list_halls(db: AsyncSession, *, only_active: bool = True) -> list[Hall]:
    return await halls_repo.list_all(db, only_active=only_active)


async def update_hall(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    hall_id: uuid.UUID,
    name: str | None = None,
    is_active: bool | None = None,
) -> Hall:
    hall = await halls_repo.get(db, hall_id)
    if hall is None:
        raise LookupError("hall_not_found")
    if name is not None:
        name = name.strip()
        existing = await halls_repo.get_by_name(db, name)
        if existing is not None and existing.id != hall.id:
            raise HallAlreadyExists(name)
        hall.name = name
    if is_active is not None:
        hall.is_active = is_active
    await db.flush()
    await audit.record(
        db,
        actor_id=actor_id,
        action="update",
        entity_type="hall",
        entity_id=str(hall.id),
        details={"name": hall.name, "is_active": hall.is_active},
    )
    return hall


async def deactivate_hall(
    db: AsyncSession, *, actor_id: uuid.UUID, hall_id: uuid.UUID
) -> None:
    hall = await halls_repo.get(db, hall_id)
    if hall is None:
        raise LookupError("hall_not_found")
    hall.is_active = False
    await db.flush()
    await audit.record(
        db,
        actor_id=actor_id,
        action="delete",
        entity_type="hall",
        entity_id=str(hall.id),
        details={"soft": True},
    )
