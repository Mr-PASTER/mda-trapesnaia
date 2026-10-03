import datetime as dt

from sqlalchemy import select

from app.models import (
    Day, DayHallMeal, Hall, MealKind, RuleKind, ScheduleRule,
    ScheduleRuleDate, ScheduleRuleHall, ScheduleRuleMeal, ScheduleRuleWeekday,
)
from app.services import calendar


async def _add_rule(db_session, *, kind, hall_id, meals, weekdays=None, dates=None):
    rule = ScheduleRule(kind=kind)
    db_session.add(rule)
    await db_session.flush()
    for wd in weekdays or []:
        db_session.add(ScheduleRuleWeekday(rule_id=rule.id, weekday=wd))
    for d in dates or []:
        db_session.add(ScheduleRuleDate(rule_id=rule.id, specific_date=d))
    for mk in meals:
        db_session.add(ScheduleRuleMeal(rule_id=rule.id, meal_kind=mk))
    db_session.add(ScheduleRuleHall(rule_id=rule.id, hall_id=hall_id))
    await db_session.flush()
    return rule


async def _served(db_session, day_date, hall_id, meal_kind) -> bool:
    day = (await db_session.execute(select(Day).where(Day.date == day_date))).scalar_one()
    row = (await db_session.execute(
        select(DayHallMeal).where(
            DayHallMeal.day_id == day.id,
            DayHallMeal.hall_id == hall_id,
            DayHallMeal.meal_kind == meal_kind,
        )
    )).scalar_one()
    return row.is_served


async def test_recurring_rule_disables_meal_on_weekday(db_session):
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    sunday = dt.date(2026, 10, 4)
    assert sunday.weekday() == 6
    await _add_rule(db_session, kind=RuleKind.recurring, hall_id=hall.id,
                    meals=[MealKind.breakfast], weekdays=[6])

    await calendar.regenerate_range(db_session, sunday, sunday)
    assert await _served(db_session, sunday, hall.id, MealKind.breakfast) is False
    assert await _served(db_session, sunday, hall.id, MealKind.lunch) is True

    monday = dt.date(2026, 10, 5)
    await calendar.regenerate_range(db_session, monday, monday)
    assert await _served(db_session, monday, hall.id, MealKind.breakfast) is True


async def test_one_off_rule_disables_all_meals_on_date(db_session):
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    holiday = dt.date(2026, 1, 1)
    await _add_rule(db_session, kind=RuleKind.one_off, hall_id=hall.id,
                    meals=list(MealKind), dates=[holiday])
    await calendar.regenerate_range(db_session, holiday, holiday)
    for mk in MealKind:
        assert await _served(db_session, holiday, hall.id, mk) is False


async def test_regeneration_restores_meal_after_rule_deactivated(db_session):
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    sunday = dt.date(2026, 10, 4)
    rule = await _add_rule(db_session, kind=RuleKind.recurring, hall_id=hall.id,
                           meals=[MealKind.breakfast], weekdays=[6])
    await calendar.regenerate_range(db_session, sunday, sunday)
    assert await _served(db_session, sunday, hall.id, MealKind.breakfast) is False

    rule.is_active = False
    await db_session.flush()
    await calendar.regenerate_range(db_session, sunday, sunday)
    assert await _served(db_session, sunday, hall.id, MealKind.breakfast) is True


async def test_inactive_hall_gets_no_rows(db_session):
    hall = Hall(name="Зал X", is_active=False)
    db_session.add(hall)
    await db_session.flush()

    d = dt.date(2026, 10, 6)
    await calendar.regenerate_range(db_session, d, d)
    day = (await db_session.execute(select(Day).where(Day.date == d))).scalar_one()
    rows = (await db_session.execute(
        select(DayHallMeal).where(DayHallMeal.day_id == day.id)
    )).scalars().all()
    assert rows == []
