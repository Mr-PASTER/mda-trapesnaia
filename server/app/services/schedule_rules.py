import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall, MealKind, RuleKind, ScheduleRule
from app.repositories import schedule_rules as repo
from app.services import audit


class InvalidRule(Exception):
    pass


class RuleNotFound(Exception):
    pass


async def get_weekdays(db, rule_id):
    return await repo.get_weekdays(db, rule_id)


async def get_dates(db, rule_id):
    return await repo.get_dates(db, rule_id)


async def get_meal_kinds(db, rule_id) -> list[MealKind]:
    return [m.meal_kind for m in await repo.get_meals(db, rule_id)]


async def get_hall_ids(db, rule_id) -> list[uuid.UUID]:
    return [h.hall_id for h in await repo.get_halls(db, rule_id)]


def _validate(
    kind: RuleKind,
    meal_kinds: list[MealKind],
    hall_ids: list[uuid.UUID],
    weekdays: list[int] | None,
    dates: list[date] | None,
) -> None:
    if not meal_kinds:
        raise InvalidRule("meal_kinds must be non-empty")
    if not hall_ids:
        raise InvalidRule("hall_ids must be non-empty")
    if kind == RuleKind.recurring:
        if not weekdays:
            raise InvalidRule("recurring rule requires weekdays")
        if dates:
            raise InvalidRule("recurring rule must not have dates")
        if any(not (0 <= w <= 6) for w in weekdays):
            raise InvalidRule("weekday must be 0..6")
    else:  # one_off
        if not dates:
            raise InvalidRule("one_off rule requires dates")
        if weekdays:
            raise InvalidRule("one_off rule must not have weekdays")


async def _validate_halls(db: AsyncSession, hall_ids: list[uuid.UUID]) -> None:
    for hid in set(hall_ids):
        hall = await db.get(Hall, hid)
        if hall is None or not hall.is_active:
            raise InvalidRule(f"hall {hid} not found or inactive")


async def create_rule(
    db: AsyncSession, *, actor_id: uuid.UUID, kind: RuleKind,
    meal_kinds: list[MealKind], hall_ids: list[uuid.UUID],
    weekdays: list[int] | None = None, dates: list[date] | None = None,
) -> ScheduleRule:
    _validate(kind, meal_kinds, hall_ids, weekdays, dates)
    await _validate_halls(db, hall_ids)

    rule = await repo.add(db, ScheduleRule(kind=kind))
    if kind == RuleKind.recurring:
        await repo.add_weekdays(db, rule.id, weekdays or [])
    else:
        await repo.add_dates(db, rule.id, dates or [])
    await repo.add_meals(db, rule.id, meal_kinds)
    await repo.add_halls(db, rule.id, hall_ids)

    await audit.record(
        db, actor_id=actor_id, action="create", entity_type="schedule_rule",
        entity_id=str(rule.id),
        details={"kind": kind.value, "meals": [m.value for m in meal_kinds],
                 "halls": [str(h) for h in hall_ids]},
    )
    return rule


async def list_rules(db: AsyncSession, *, only_active: bool = True) -> list[ScheduleRule]:
    return await repo.list_all(db, only_active=only_active)


async def update_rule(
    db: AsyncSession, *, actor_id: uuid.UUID, rule_id: uuid.UUID,
    is_active: bool | None = None, meal_kinds: list[MealKind] | None = None,
    hall_ids: list[uuid.UUID] | None = None, weekdays: list[int] | None = None,
    dates: list[date] | None = None,
) -> ScheduleRule:
    rule = await repo.get(db, rule_id)
    if rule is None:
        raise RuleNotFound(str(rule_id))

    cur_meals = meal_kinds if meal_kinds is not None else await get_meal_kinds(db, rule_id)
    cur_halls = hall_ids if hall_ids is not None else await get_hall_ids(db, rule_id)
    cur_weekdays = weekdays if weekdays is not None else [w.weekday for w in await repo.get_weekdays(db, rule_id)]
    cur_dates = dates if dates is not None else [d.specific_date for d in await repo.get_dates(db, rule_id)]
    _validate(rule.kind, cur_meals, cur_halls, cur_weekdays, cur_dates)
    await _validate_halls(db, cur_halls)

    if is_active is not None:
        rule.is_active = is_active
    if meal_kinds is not None or hall_ids is not None or weekdays is not None or dates is not None:
        await repo.clear_children(db, rule_id)
        if rule.kind == RuleKind.recurring:
            await repo.add_weekdays(db, rule_id, cur_weekdays)
        else:
            await repo.add_dates(db, rule_id, cur_dates)
        await repo.add_meals(db, rule_id, cur_meals)
        await repo.add_halls(db, rule_id, cur_halls)
    await db.flush()

    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="schedule_rule",
        entity_id=str(rule.id), details={"is_active": rule.is_active},
    )
    return rule


async def deactivate_rule(db: AsyncSession, *, actor_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    rule = await repo.get(db, rule_id)
    if rule is None:
        raise RuleNotFound(str(rule_id))
    rule.is_active = False
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="delete", entity_type="schedule_rule",
        entity_id=str(rule.id), details={"soft": True},
    )
