import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ScheduleRule, ScheduleRuleDate, ScheduleRuleHall, ScheduleRuleMeal, ScheduleRuleWeekday,
)


async def get(db: AsyncSession, rule_id: uuid.UUID) -> ScheduleRule | None:
    return await db.get(ScheduleRule, rule_id)


async def list_all(db: AsyncSession, *, only_active: bool) -> list[ScheduleRule]:
    stmt = select(ScheduleRule).order_by(ScheduleRule.created_at)
    if only_active:
        stmt = stmt.where(ScheduleRule.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def get_weekdays(db: AsyncSession, rule_id) -> list[ScheduleRuleWeekday]:
    stmt = select(ScheduleRuleWeekday).where(ScheduleRuleWeekday.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_dates(db: AsyncSession, rule_id) -> list[ScheduleRuleDate]:
    stmt = select(ScheduleRuleDate).where(ScheduleRuleDate.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_meals(db: AsyncSession, rule_id) -> list[ScheduleRuleMeal]:
    stmt = select(ScheduleRuleMeal).where(ScheduleRuleMeal.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_halls(db: AsyncSession, rule_id) -> list[ScheduleRuleHall]:
    stmt = select(ScheduleRuleHall).where(ScheduleRuleHall.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def add(db: AsyncSession, rule: ScheduleRule) -> ScheduleRule:
    db.add(rule)
    await db.flush()
    return rule


async def clear_children(db: AsyncSession, rule_id) -> None:
    for model in (ScheduleRuleWeekday, ScheduleRuleDate, ScheduleRuleMeal, ScheduleRuleHall):
        await db.execute(delete(model).where(model.rule_id == rule_id))


async def add_weekdays(db, rule_id, weekdays):
    for wd in sorted(set(weekdays)):
        db.add(ScheduleRuleWeekday(rule_id=rule_id, weekday=wd))
    await db.flush()


async def add_dates(db, rule_id, dates):
    for d in sorted(set(dates)):
        db.add(ScheduleRuleDate(rule_id=rule_id, specific_date=d))
    await db.flush()


async def add_meals(db, rule_id, meal_kinds):
    for mk in sorted(set(meal_kinds), key=lambda m: m.value):
        db.add(ScheduleRuleMeal(rule_id=rule_id, meal_kind=mk))
    await db.flush()


async def add_halls(db, rule_id, hall_ids):
    for hid in sorted(set(hall_ids)):
        db.add(ScheduleRuleHall(rule_id=rule_id, hall_id=hid))
    await db.flush()
