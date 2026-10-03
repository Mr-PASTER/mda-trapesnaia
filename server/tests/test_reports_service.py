import datetime as dt

from app.models import (
    Day, DayHallMeal, Hall, MealKind, MealType, Request, RequestItem, User, UserHall, UserRole,
)
from app.services import reports


async def _setup(db_session):
    hall = Hall(name="Зал №1")
    meat = MealType(name="Мясо", sort_order=1)
    fish = MealType(name="Рыба", sort_order=2)
    db_session.add_all([hall, meat, fish])
    await db_session.flush()

    def eater(login, mt_id):
        return User(login=login, password_hash="x", full_name=login,
                    role=UserRole.eater, default_meal_type_id=mt_id)

    e1 = eater("e1", meat.id)
    e2 = eater("e2", fish.id)
    db_session.add_all([e1, e2])
    await db_session.flush()
    db_session.add_all([UserHall(user_id=e1.id, hall_id=hall.id),
                        UserHall(user_id=e2.id, hall_id=hall.id)])
    day = Day(date=dt.date(2026, 6, 10))
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk,
                                   is_served=(mk != MealKind.snack)))
    await db_session.flush()
    return hall, meat, fish, e1, e2


async def test_daily_report_defaults(db_session):
    hall, meat, fish, e1, e2 = await _setup(db_session)
    rep = await reports.build_daily_report(db_session, on_date=dt.date(2026, 6, 10))
    # по умолчанию никто не ходит -> нули
    assert rep.grand_total == 0
    hall_rep = rep.halls[0]
    assert len(hall_rep.meals) == 4
    assert all(m.total == 0 for m in hall_rep.meals)
    # все активные типы присутствуют
    assert {t.name for t in hall_rep.meals[0].by_type} == {"Мясо", "Рыба"}


async def test_daily_report_counts_going_and_reserve(db_session):
    hall, meat, fish, e1, e2 = await _setup(db_session)
    # заявка e1: идёт на завтрак (Мясо, обычная)
    req = Request(user_id=e1.id, date=dt.date(2026, 6, 10), meal_type_id=meat.id, version=1)
    db_session.add(req)
    await db_session.flush()
    db_session.add_all([
        RequestItem(request_id=req.id, meal_kind=MealKind.breakfast, is_going=True, is_reserve=False),
        RequestItem(request_id=req.id, meal_kind=MealKind.lunch, is_going=True, is_reserve=True),
    ])
    # заявка e2: идёт на завтрак (Рыба, резерв)
    req2 = Request(user_id=e2.id, date=dt.date(2026, 6, 10), meal_type_id=fish.id, version=1)
    db_session.add(req2)
    await db_session.flush()
    db_session.add(RequestItem(request_id=req2.id, meal_kind=MealKind.breakfast,
                               is_going=True, is_reserve=True))
    await db_session.flush()

    rep = await reports.build_daily_report(db_session, on_date=dt.date(2026, 6, 10))
    hall_rep = rep.halls[0]
    breakfast = next(m for m in hall_rep.meals if m.meal_kind == MealKind.breakfast)
    by_name = {t.name: t.count for t in breakfast.by_type}
    assert by_name["Мясо"] == 1 and by_name["Рыба"] == 1
    assert breakfast.total == 2
    reserve_by_name = {t.name: t.count for t in breakfast.reserve_by_type}
    assert reserve_by_name["Рыба"] == 1 and reserve_by_name["Мясо"] == 0
    assert breakfast.reserve_total == 1

    # полдник не подаётся -> не учитывается даже если бы шли
    snack = next(m for m in hall_rep.meals if m.meal_kind == MealKind.snack)
    assert snack.total == 0
