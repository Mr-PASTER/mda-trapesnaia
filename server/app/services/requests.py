import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MealKind, MealType, Request, RequestItem, User, UserMealDefault, UserRole,
)
from app.services import access, audit, deadline


class DayLocked(Exception):
    pass


class VersionConflict(Exception):
    pass


class MealTypeInvalid(Exception):
    pass


def _apply_meals(
    items: dict[MealKind, RequestItem], meals: dict[MealKind, bool], *, reserve_changes: bool
) -> None:
    for meal_kind, going in meals.items():
        item = items.get(meal_kind)
        if item is None:
            continue
        if not going:
            item.is_going = False
            item.is_reserve = False
        else:
            if reserve_changes and item.is_going is False:
                item.is_reserve = True
            item.is_going = True


def _mark_all_going_reserve(items: dict[MealKind, RequestItem]) -> None:
    for item in items.values():
        if item.is_going:
            item.is_reserve = True


async def _load_items(db: AsyncSession, request_id: uuid.UUID) -> dict[MealKind, RequestItem]:
    rows = (
        await db.execute(select(RequestItem).where(RequestItem.request_id == request_id))
    ).scalars().all()
    return {r.meal_kind: r for r in rows}


async def save_day(
    db: AsyncSession, *, actor: User, target: User, day_date: date,
    meal_type_id: uuid.UUID | None, meals: dict[MealKind, bool], version: int | None,
) -> Request:
    await access.ensure_can_edit_user(db, actor=actor, target=target)

    locked = await deadline.is_locked(db, day_date)
    is_admin_edit = actor.id != target.id and actor.role == UserRole.admin
    if locked and not is_admin_edit:
        raise DayLocked()
    reserve_changes = is_admin_edit and locked

    if meal_type_id is not None:
        mt = await db.get(MealType, meal_type_id)
        if mt is None or not mt.is_active:
            raise MealTypeInvalid(str(meal_type_id))

    req = (
        await db.execute(
            select(Request)
            .where(Request.user_id == target.id, Request.date == day_date)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if req is None:
        type_for_day = meal_type_id if meal_type_id is not None else target.default_meal_type_id
        req = Request(user_id=target.id, date=day_date, meal_type_id=type_for_day, version=1)
        db.add(req)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise VersionConflict()

        defaults_rows = (
            await db.execute(
                select(UserMealDefault).where(UserMealDefault.user_id == target.id)
            )
        ).scalars().all()
        defaults = {r.meal_kind: r.is_going for r in defaults_rows}
        items = {}
        for meal_kind in MealKind:
            item = RequestItem(
                request_id=req.id,
                meal_kind=meal_kind,
                is_going=defaults.get(meal_kind, False),
                is_reserve=False,
            )
            db.add(item)
            items[meal_kind] = item
        await db.flush()

        if reserve_changes and meal_type_id is not None and meal_type_id != target.default_meal_type_id:
            _mark_all_going_reserve(items)
        _apply_meals(items, meals, reserve_changes=reserve_changes)
        await db.flush()
    else:
        if version is None or version != req.version:
            raise VersionConflict()
        items = await _load_items(db, req.id)

        if meal_type_id is not None and meal_type_id != req.meal_type_id:
            if reserve_changes:
                _mark_all_going_reserve(items)
            req.meal_type_id = meal_type_id
        _apply_meals(items, meals, reserve_changes=reserve_changes)
        req.version = req.version + 1
        await db.flush()

    await audit.record(
        db, actor_id=actor.id, action="save_day", entity_type="request",
        entity_id=str(req.id),
        details={"user_id": str(target.id), "date": day_date.isoformat(),
                 "reserve": reserve_changes, "by_admin": is_admin_edit},
    )
    return req
