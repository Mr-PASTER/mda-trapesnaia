import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserHall


async def get_by_login(db: AsyncSession, login: str) -> User | None:
    result = await db.execute(select(User).where(User.login == login.lower().strip()))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def list_all(
    db: AsyncSession, *, role=None, hall_id=None, only_active: bool = False
) -> list[User]:
    stmt = select(User).order_by(User.login)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if only_active:
        stmt = stmt.where(User.is_active.is_(True))
    if hall_id is not None:
        stmt = stmt.join(UserHall, UserHall.user_id == User.id).where(
            UserHall.hall_id == hall_id
        )
    return list((await db.execute(stmt)).scalars().all())


async def hall_ids_of(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    result = await db.execute(select(UserHall.hall_id).where(UserHall.user_id == user_id))
    return set(result.scalars().all())


async def replace_halls(db: AsyncSession, user_id: uuid.UUID, hall_ids) -> None:
    await db.execute(delete(UserHall).where(UserHall.user_id == user_id))
    for hid in hall_ids:
        db.add(UserHall(user_id=user_id, hall_id=hid))
    await db.flush()


async def add(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.flush()
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(User).where(User.id == user_id))
    await db.flush()
