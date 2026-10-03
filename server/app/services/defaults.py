import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MealKind, MealType, User, UserMealDefault
from app.services import audit


@dataclass
class Defaults:
    meal_type_id: uuid.UUID | None
    meals: dict[MealKind, bool]


class MealTypeInvalid(Exception):
    pass


async def get_defaults(db: AsyncSession, user: User) -> Defaults:
    rows = (
        await db.execute(select(UserMealDefault).where(UserMealDefault.user_id == user.id))
    ).scalars().all()
    stored = {r.meal_kind: r.is_going for r in rows}
    return Defaults(
        meal_type_id=user.default_meal_type_id,
        meals={mk: stored.get(mk, False) for mk in MealKind},
    )


async def update_defaults(
    db: AsyncSession, *, actor_id: uuid.UUID, user: User,
    meal_type_id: uuid.UUID | None, meals: dict[MealKind, bool],
) -> None:
    if meal_type_id is not None:
        mt = await db.get(MealType, meal_type_id)
        if mt is None or not mt.is_active:
            raise MealTypeInvalid(str(meal_type_id))
        user.default_meal_type_id = meal_type_id

    rows = {
        r.meal_kind: r
        for r in (
            await db.execute(select(UserMealDefault).where(UserMealDefault.user_id == user.id))
        ).scalars().all()
    }
    for meal_kind in MealKind:
        going = meals.get(meal_kind, False)
        row = rows.get(meal_kind)
        if row is None:
            db.add(UserMealDefault(user_id=user.id, meal_kind=meal_kind, is_going=going))
        else:
            row.is_going = going
    await db.flush()

    await audit.record(
        db, actor_id=actor_id, action="update_defaults", entity_type="user",
        entity_id=str(user.id),
        details={"meal_type_id": str(meal_type_id) if meal_type_id else None},
    )
