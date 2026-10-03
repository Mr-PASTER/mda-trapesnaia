import datetime as dt

import pytest

from app.models import Hall, MealKind, RuleKind, ScheduleRuleHall, ScheduleRuleWeekday, User, UserRole
from app.services import schedule_rules


async def _actor_halls(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    h1, h2 = Hall(name="Зал №1"), Hall(name="Зал №2")
    db_session.add_all([actor, h1, h2])
    await db_session.flush()
    return actor, h1, h2


async def test_create_recurring_rule(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    rule = await schedule_rules.create_rule(
        db_session, actor_id=actor.id, kind=RuleKind.recurring,
        meal_kinds=[MealKind.breakfast], hall_ids=[h1.id], weekdays=[6],
    )
    assert rule.kind == RuleKind.recurring
    wd = [w.weekday for w in await schedule_rules.get_weekdays(db_session, rule.id)]
    assert wd == [6]


async def test_recurring_requires_weekdays(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.recurring,
            meal_kinds=[MealKind.breakfast], hall_ids=[h1.id], weekdays=[], dates=[],
        )


async def test_one_off_requires_dates(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.one_off,
            meal_kinds=[MealKind.lunch], hall_ids=[h1.id], dates=[],
        )


async def test_requires_meals_and_halls(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.recurring,
            meal_kinds=[], hall_ids=[h1.id], weekdays=[6],
        )
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.recurring,
            meal_kinds=[MealKind.breakfast], hall_ids=[], weekdays=[6],
        )


async def test_deactivate_rule(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    rule = await schedule_rules.create_rule(
        db_session, actor_id=actor.id, kind=RuleKind.one_off,
        meal_kinds=[MealKind.dinner], hall_ids=[h1.id], dates=[dt.date(2026, 1, 1)],
    )
    await schedule_rules.deactivate_rule(db_session, actor_id=actor.id, rule_id=rule.id)
    assert rule.is_active is False
    assert await schedule_rules.list_rules(db_session) == []
