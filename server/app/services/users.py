import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Hall, MealType, User, UserRole
from app.repositories import users as repo
from app.services import audit

_HALL_RULES = {
    UserRole.eater: (1, 1),
    UserRole.admin: (1, None),
    UserRole.accountant: (0, 0),
    UserRole.operator: (0, 0),
}


class LoginAlreadyExists(Exception):
    pass


class InvalidHalls(Exception):
    pass


class DefaultMealTypeInvalid(Exception):
    pass


def _validate_halls(role: UserRole, hall_ids: list[uuid.UUID]) -> None:
    lo, hi = _HALL_RULES[role]
    n = len(set(hall_ids))
    if n < lo or (hi is not None and n > hi):
        raise InvalidHalls(f"role {role.value} requires {lo}..{hi} halls, got {n}")


async def _validate_hall_ids(db: AsyncSession, hall_ids: list[uuid.UUID]) -> None:
    for hid in set(hall_ids):
        hall = await db.get(Hall, hid)
        if hall is None or not hall.is_active:
            raise InvalidHalls(f"hall {hid} not found or inactive")


async def _validate_default_type(db: AsyncSession, meal_type_id: uuid.UUID | None) -> None:
    if meal_type_id is None:
        return
    mt = await db.get(MealType, meal_type_id)
    if mt is None or not mt.is_active:
        raise DefaultMealTypeInvalid(str(meal_type_id))


async def create_user(
    db: AsyncSession, *, actor_id: uuid.UUID, login: str, password: str,
    full_name: str, role: UserRole, hall_ids: list[uuid.UUID],
    default_meal_type_id: uuid.UUID | None = None,
) -> User:
    login = login.lower().strip()
    if await repo.get_by_login(db, login) is not None:
        raise LoginAlreadyExists(login)
    _validate_halls(role, hall_ids)
    await _validate_hall_ids(db, hall_ids)
    await _validate_default_type(db, default_meal_type_id)

    user = await repo.add(
        db,
        User(
            login=login,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            default_meal_type_id=default_meal_type_id,
        ),
    )
    await repo.replace_halls(db, user.id, hall_ids)
    await audit.record(
        db, actor_id=actor_id, action="create", entity_type="user",
        entity_id=str(user.id),
        details={"login": login, "role": role.value, "halls": [str(h) for h in hall_ids]},
    )
    return user


async def list_users(
    db: AsyncSession, *, role: UserRole | None = None,
    hall_id: uuid.UUID | None = None, only_active: bool = False,
) -> list[User]:
    return await repo.list_all(db, role=role, hall_id=hall_id, only_active=only_active)


async def update_user(
    db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID,
    full_name: str | None = None, role: UserRole | None = None,
    default_meal_type_id: uuid.UUID | None = None,
) -> User:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    if full_name is not None:
        user.full_name = full_name
    if role is not None and role != user.role:
        current = await repo.hall_ids_of(db, user.id)
        _validate_halls(role, list(current))
        user.role = role
    if default_meal_type_id is not None:
        await _validate_default_type(db, default_meal_type_id)
        user.default_meal_type_id = default_meal_type_id
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="user",
        entity_id=str(user.id),
        details={"full_name": user.full_name, "role": user.role.value},
    )
    return user


async def set_password(
    db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, password: str
) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    user.password_hash = hash_password(password)
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="set_password", entity_type="user",
        entity_id=str(user.id), details=None,
    )


async def set_halls(
    db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID,
    hall_ids: list[uuid.UUID],
) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    _validate_halls(user.role, hall_ids)
    await _validate_hall_ids(db, hall_ids)
    await repo.replace_halls(db, user.id, hall_ids)
    await audit.record(
        db, actor_id=actor_id, action="set_halls", entity_type="user",
        entity_id=str(user.id), details={"halls": [str(h) for h in hall_ids]},
    )


async def deactivate_user(db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    user.is_active = False
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="delete", entity_type="user",
        entity_id=str(user.id), details={"soft": True},
    )


async def hard_delete_user(db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    details = {"login": user.login, "soft": False}
    await audit.record(
        db, actor_id=actor_id, action="hard_delete", entity_type="user",
        entity_id=str(user_id), details=details,
    )
    await repo.delete_user(db, user_id)
