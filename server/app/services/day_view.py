import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Day, DayHallMeal, MealKind, Request, RequestItem, User, UserMealDefault,
)
from app.services import access, deadline


@dataclass
class MealState:
    meal_kind: MealKind
    is_served: bool
    is_going: bool
    is_reserve: bool


@dataclass
class DayState:
    date: date
    meal_type_id: uuid.UUID | None
    items: list[MealState]
    version: int | None
    has_request: bool
    deadline_at: datetime
    editable: bool


async def _served_map(db: AsyncSession, hall_ids: set[uuid.UUID], day_date: date) -> dict[MealKind, bool]:
    served = {mk: False for mk in MealKind}
    if not hall_ids:
        return served
    stmt = (
        select(DayHallMeal.meal_kind, DayHallMeal.is_served)
        .join(Day, Day.id == DayHallMeal.day_id)
        .where(Day.date == day_date, DayHallMeal.hall_id.in_(hall_ids))
    )
    for meal_kind, is_served in (await db.execute(stmt)).all():
        served[meal_kind] = served[meal_kind] or is_served
    return served


async def get_day_state(
    db: AsyncSession, *, user: User, day_date: date, now: datetime | None = None
) -> DayState:
    hall_ids = await access.hall_ids_of(db, user.id)
    served = await _served_map(db, hall_ids, day_date)

    req = (
        await db.execute(
            select(Request).where(Request.user_id == user.id, Request.date == day_date)
        )
    ).scalar_one_or_none()

    if req is not None:
        items = {
            i.meal_kind: i
            for i in (
                await db.execute(select(RequestItem).where(RequestItem.request_id == req.id))
            ).scalars().all()
        }
        meal_type_id = req.meal_type_id
        version = req.version
        has_request = True
        going = {mk: (items[mk].is_going if mk in items else False) for mk in MealKind}
        reserve = {mk: (items[mk].is_reserve if mk in items else False) for mk in MealKind}
    else:
        rows = (
            await db.execute(
                select(UserMealDefault).where(UserMealDefault.user_id == user.id)
            )
        ).scalars().all()
        defaults = {r.meal_kind: r.is_going for r in rows}
        meal_type_id = user.default_meal_type_id
        version = None
        has_request = False
        going = {mk: defaults.get(mk, False) for mk in MealKind}
        reserve = {mk: False for mk in MealKind}

    deadline_at = await deadline.deadline_for(db, day_date)
    locked = await deadline.is_locked(db, day_date, now=now)

    return DayState(
        date=day_date,
        meal_type_id=meal_type_id,
        items=[
            MealState(
                meal_kind=mk,
                is_served=served[mk],
                is_going=going[mk],
                is_reserve=reserve[mk],
            )
            for mk in MealKind
        ],
        version=version,
        has_request=has_request,
        deadline_at=deadline_at,
        editable=not locked,
    )
