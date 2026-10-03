import datetime as dt

from app.models import (
    Day, DayHallMeal, Hall, MealKind, MealType, User, UserHall, UserMealDefault, UserRole,
)
from app.services import day_view


async def _setup(db_session):
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([hall, mt, user])
    await db_session.flush()
    db_session.add(UserHall(user_id=user.id, hall_id=hall.id))
    user.default_meal_type_id = mt.id
    day = Day(date=dt.date(2026, 10, 10))
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk,
                                   is_served=(mk != MealKind.snack)))
    db_session.add_all([
        UserMealDefault(user_id=user.id, meal_kind=MealKind.breakfast, is_going=True),
        UserMealDefault(user_id=user.id, meal_kind=MealKind.lunch, is_going=True),
    ])
    await db_session.flush()
    return hall, mt, user


async def test_defaults_when_no_request(db_session):
    hall, mt, user = await _setup(db_session)
    state = await day_view.get_day_state(db_session, user=user, day_date=dt.date(2026, 10, 10))
    assert state.available is True
    assert state.editable is True
    assert state.has_request is False
    assert state.version is None
    assert state.meal_type_id == mt.id
    served = {i.meal_kind: i.is_served for i in state.items}
    assert served[MealKind.snack] is False
    going = {i.meal_kind: i.is_going for i in state.items}
    assert going[MealKind.breakfast] is True
    assert going[MealKind.dinner] is False


async def test_not_available_when_no_day_row(db_session):
    hall, mt, user = await _setup(db_session)
    state = await day_view.get_day_state(db_session, user=user, day_date=dt.date(2026, 10, 11))
    assert state.available is False
    assert state.editable is False
    served = {i.meal_kind: i.is_served for i in state.items}
    assert all(v is False for v in served.values())
