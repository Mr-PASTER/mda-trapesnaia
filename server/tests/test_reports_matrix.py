import datetime as dt

from app.models import (
    Day,
    DayHallMeal,
    Hall,
    MealKind,
    MealType,
    User,
    UserHall,
    UserMealDefault,
    UserRole,
)
from app.services import reports


async def test_matrix_has_counts_per_date_and_hall(db_session):
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([hall, mt, user])
    await db_session.flush()
    db_session.add(UserHall(user_id=user.id, hall_id=hall.id))
    user.default_meal_type_id = mt.id
    for offset in (0, 1):
        day = Day(date=dt.date(2026, 6, 10) + dt.timedelta(days=offset))
        db_session.add(day)
        await db_session.flush()
        for mk in MealKind:
            db_session.add(
                DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk, is_served=True)
            )
    db_session.add(
        UserMealDefault(user_id=user.id, meal_kind=MealKind.breakfast, is_going=True)
    )
    await db_session.flush()

    matrix = await reports.build_period_matrix(
        db_session, start=dt.date(2026, 6, 10), end=dt.date(2026, 6, 11)
    )

    assert matrix.dates == [dt.date(2026, 6, 10), dt.date(2026, 6, 11)]
    assert [h.name for h in matrix.halls] == ["Зал №1"]
    for day_date in matrix.dates:
        acc = matrix.counts[day_date][hall.id]
        assert acc.by_type[MealKind.breakfast][mt.id] == 1
        assert acc.by_type[MealKind.lunch][mt.id] == 0
