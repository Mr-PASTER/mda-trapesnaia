import datetime as dt
from datetime import time
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    Day, DayHallMeal, Hall, MealKind, MealType, RequestItem, User, UserHall,
    UserMealDefault, UserRole,
)
from app.services import requests as svc
from app.services import settings as settings_service

TZ = ZoneInfo("Europe/Moscow")
DAY = dt.date(2026, 10, 10)


async def _setup(db_session, *, k=2, h=time(13, 0)):
    op = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    eater = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([op, hall, mt, eater])
    await db_session.flush()
    db_session.add(UserHall(user_id=eater.id, hall_id=hall.id))
    eater.default_meal_type_id = mt.id
    day = Day(date=DAY)
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk, is_served=True))
    db_session.add(UserMealDefault(user_id=eater.id, meal_kind=MealKind.breakfast, is_going=True))
    await settings_service.update_settings(
        db_session, actor_id=op.id, deadline_offset_days=k, deadline_time=h
    )
    await db_session.flush()
    return op, hall, mt, eater


async def _items(db_session, request_id):
    from sqlalchemy import select

    rows = (await db_session.execute(
        select(RequestItem).where(RequestItem.request_id == request_id)
    )).scalars().all()
    return {r.meal_kind: r for r in rows}


async def test_lazy_create_from_defaults(db_session):
    op, hall, mt, eater = await _setup(db_session)
    # до дедлайна
    now = dt.datetime(2026, 10, 8, 14, 0, tzinfo=TZ)
    req = await svc.save_day(
        db_session, actor=eater, target=eater, day_date=DAY,
        meal_type_id=mt.id, meals={MealKind.lunch: True}, version=None,
    )
    assert req.version == 1
    items = await _items(db_session, req.id)
    assert items[MealKind.breakfast].is_going is True   # из дефолтов
    assert items[MealKind.lunch].is_going is True
    assert items[MealKind.dinner].is_going is False
    assert all(i.is_reserve is False for i in items.values())


async def test_eater_locked_after_deadline(db_session):
    op, hall, mt, eater = await _setup(db_session, k=2, h=time(13, 0))
    # now после дедлайна (дедлайн 08.10 13:00) -> сымитируем через реальное "сейчас"
    # используем day в прошлом, чтобы дедлайн точно прошёл
    past_day = dt.date(2020, 1, 1)
    with pytest.raises(svc.DayLocked):
        await svc.save_day(
            db_session, actor=eater, target=eater, day_date=past_day,
            meal_type_id=mt.id, meals={MealKind.lunch: True}, version=None,
        )


async def test_version_conflict(db_session):
    op, hall, mt, eater = await _setup(db_session)
    req = await svc.save_day(
        db_session, actor=eater, target=eater, day_date=DAY,
        meal_type_id=mt.id, meals={}, version=None,
    )
    with pytest.raises(svc.VersionConflict):
        await svc.save_day(
            db_session, actor=eater, target=eater, day_date=DAY,
            meal_type_id=mt.id, meals={MealKind.dinner: True}, version=999,
        )
    # верная версия — ок, версия растёт
    # req и req2 — один и тот же identity-mapped объект, поэтому фиксируем
    # исходную версию заранее, иначе сравнение вырождается в v == v + 1.
    first_version = req.version
    req2 = await svc.save_day(
        db_session, actor=eater, target=eater, day_date=DAY,
        meal_type_id=mt.id, meals={MealKind.dinner: True}, version=first_version,
    )
    assert req2.version == first_version + 1


async def test_admin_edit_after_deadline_sets_reserve(db_session):
    op, hall, mt, eater = await _setup(db_session)
    admin = User(login="adm", password_hash="x", full_name="Админ", role=UserRole.admin)
    db_session.add(admin)
    await db_session.flush()
    db_session.add(UserHall(user_id=admin.id, hall_id=hall.id))
    await db_session.flush()

    # создаём заявку в прошлом через админа после дедлайна -> резерв
    past = dt.date(2020, 1, 1)
    day = Day(date=past)
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk, is_served=True))
    await db_session.flush()

    req = await svc.save_day(
        db_session, actor=admin, target=eater, day_date=past,
        meal_type_id=mt.id, meals={MealKind.dinner: True}, version=None,
    )
    items = await _items(db_session, req.id)
    assert items[MealKind.dinner].is_reserve is True
