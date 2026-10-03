import datetime as dt
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DayHallMeal, MealKind, RuleKind, ScheduleRule, ScheduleRuleDate,
    ScheduleRuleHall, ScheduleRuleMeal, ScheduleRuleWeekday,
)
from app.repositories import calendar as cal_repo
from app.services import settings as settings_service


async def _rule_ids_for_hall(db: AsyncSession, hall_id) -> list:
    stmt = (
        select(ScheduleRuleHall.rule_id)
        .join(ScheduleRule, ScheduleRule.id == ScheduleRuleHall.rule_id)
        .where(ScheduleRuleHall.hall_id == hall_id, ScheduleRule.is_active.is_(True))
    )
    return list((await db.execute(stmt)).scalars().all())


async def _disabled_meals(db: AsyncSession, day_date: dt.date, hall_id) -> set[MealKind]:
    disabled: set[MealKind] = set()
    rule_ids = await _rule_ids_for_hall(db, hall_id)
    if not rule_ids:
        return disabled

    rules = {
        r.id: r
        for r in (await db.execute(
            select(ScheduleRule).where(ScheduleRule.id.in_(rule_ids))
        )).scalars().all()
    }

    for rule_id, rule in rules.items():
        matched = False
        if rule.kind == RuleKind.recurring:
            wds = set((await db.execute(
                select(ScheduleRuleWeekday.weekday).where(ScheduleRuleWeekday.rule_id == rule_id)
            )).scalars().all())
            matched = day_date.weekday() in wds
        else:
            dts = set((await db.execute(
                select(ScheduleRuleDate.specific_date).where(ScheduleRuleDate.rule_id == rule_id)
            )).scalars().all())
            matched = day_date in dts
        if matched:
            meals = (await db.execute(
                select(ScheduleRuleMeal.meal_kind).where(ScheduleRuleMeal.rule_id == rule_id)
            )).scalars().all()
            disabled |= set(meals)
    return disabled


async def materialize_day(db: AsyncSession, day_date: dt.date) -> None:
    day = await cal_repo.get_or_create_day(db, day_date)
    halls = await cal_repo.list_active_halls(db)
    await cal_repo.clear_day_meals(db, day.id)

    rows: list[DayHallMeal] = []
    for hall in halls:
        disabled = await _disabled_meals(db, day_date, hall.id)
        for meal_kind in MealKind:
            rows.append(
                DayHallMeal(
                    day_id=day.id,
                    hall_id=hall.id,
                    meal_kind=meal_kind,
                    is_served=meal_kind not in disabled,
                )
            )
    await cal_repo.add_day_meals(db, rows)


def _iter_dates(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


async def regenerate_range(db: AsyncSession, start: dt.date, end: dt.date) -> None:
    if end < start:
        return
    for day_date in _iter_dates(start, end):
        await materialize_day(db, day_date)


async def regenerate_horizon(db: AsyncSession) -> None:
    config = await settings_service.get_settings(db)
    today = dt.date.today()
    await regenerate_range(db, today, today + dt.timedelta(days=config.generation_days))
