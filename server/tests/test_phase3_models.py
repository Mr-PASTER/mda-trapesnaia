import datetime as dt

from sqlalchemy import select

from app.models import (
    Day,
    DayHallMeal,
    Hall,
    MealKind,
    RuleKind,
    ScheduleRule,
    ScheduleRuleHall,
    ScheduleRuleMeal,
    ScheduleRuleWeekday,
)


async def test_create_rule_with_children_and_day(db_session):
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    rule = ScheduleRule(kind=RuleKind.recurring)
    db_session.add(rule)
    await db_session.flush()
    db_session.add_all(
        [
            ScheduleRuleWeekday(rule_id=rule.id, weekday=6),
            ScheduleRuleMeal(rule_id=rule.id, meal_kind=MealKind.breakfast),
            ScheduleRuleHall(rule_id=rule.id, hall_id=hall.id),
        ]
    )
    await db_session.flush()

    day = Day(date=dt.date(2026, 10, 4))
    db_session.add(day)
    await db_session.flush()
    db_session.add(
        DayHallMeal(
            day_id=day.id,
            hall_id=hall.id,
            meal_kind=MealKind.breakfast,
            is_served=False,
        )
    )
    await db_session.flush()

    meals = (await db_session.execute(select(DayHallMeal))).scalars().all()
    assert len(meals) == 1 and meals[0].is_served is False
