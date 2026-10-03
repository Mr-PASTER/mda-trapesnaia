import datetime as dt
import uuid

import pytest

from app.core.security import hash_password
from app.models import Day, DayHallMeal, Hall, MealKind, User, UserHall, UserRole

FP = "dev-1"
DAY_OFFSET = 30


@pytest.fixture
async def admin_headers(client, db_session):
    hall = Hall(name="Зал №1")
    admin = User(
        login="adm",
        password_hash=hash_password("apass"),
        full_name="Админ",
        role=UserRole.admin,
    )
    eater = User(
        login="ivan",
        password_hash=hash_password("ipass"),
        full_name="Иван",
        role=UserRole.eater,
    )
    db_session.add_all([hall, admin, eater])
    await db_session.flush()
    db_session.add_all(
        [
            UserHall(user_id=admin.id, hall_id=hall.id),
            UserHall(user_id=eater.id, hall_id=hall.id),
        ]
    )
    day = Day(date=dt.date.today() + dt.timedelta(days=DAY_OFFSET))
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(
            DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk, is_served=True)
        )
    await db_session.commit()
    r = await client.post(
        "/api/v1/auth/login",
        json={"login": "adm", "password": "apass"},
        headers={"X-Device-Fingerprint": FP},
    )
    return {
        "X-Device-Fingerprint": FP,
    }, hall.id


async def test_admin_lists_eaters_of_hall(client, admin_headers):
    headers, hall_id = admin_headers
    r = await client.get(f"/api/v1/admin/users?hall_id={hall_id}", headers=headers)
    assert r.status_code == 200
    logins = [u["login"] for u in r.json()]
    assert "ivan" in logins


async def test_admin_edits_eater_future_day(client, admin_headers):
    headers, hall_id = admin_headers
    r = await client.get(f"/api/v1/admin/users?hall_id={hall_id}", headers=headers)
    user_id = r.json()[0]["id"]
    future = (dt.date.today() + dt.timedelta(days=DAY_OFFSET)).isoformat()

    r = await client.put(
        f"/api/v1/admin/requests/{user_id}/{future}",
        headers=headers,
        json={"meals": {"breakfast": True}, "version": None},
    )
    assert r.status_code == 200
    assert r.json()["has_request"] is True

    # день без строки в days -> недоступен для правки
    missing = (dt.date.today() + dt.timedelta(days=DAY_OFFSET + 1)).isoformat()
    r = await client.put(
        f"/api/v1/admin/requests/{user_id}/{missing}",
        headers=headers,
        json={"meals": {"breakfast": True}, "version": None},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "day_not_available"


async def _eater_id(client, headers, hall_id) -> str:
    r = await client.get(f"/api/v1/admin/users?hall_id={hall_id}", headers=headers)
    assert r.status_code == 200
    return next(u["id"] for u in r.json() if u["login"] == "ivan")


async def test_admin_reads_eater_calendar_and_defaults(client, admin_headers):
    headers, hall_id = admin_headers
    user_id = await _eater_id(client, headers, hall_id)
    day = (dt.date.today() + dt.timedelta(days=DAY_OFFSET)).isoformat()

    r = await client.get(f"/api/v1/admin/users/{user_id}/defaults", headers=headers)
    assert r.status_code == 200
    assert "default_meal_type_id" in r.json()
    assert "meals" in r.json()

    r = await client.get(
        f"/api/v1/admin/users/{user_id}/calendar?from={day}&to={day}", headers=headers
    )
    assert r.status_code == 200
    assert [d["date"] for d in r.json()] == [day]


async def test_admin_calendar_available_flag(client, admin_headers):
    headers, hall_id = admin_headers
    user_id = await _eater_id(client, headers, hall_id)
    existing = (dt.date.today() + dt.timedelta(days=DAY_OFFSET)).isoformat()
    missing = (dt.date.today() + dt.timedelta(days=DAY_OFFSET + 1)).isoformat()
    r = await client.get(
        f"/api/v1/admin/users/{user_id}/calendar?from={existing}&to={missing}",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert [d["date"] for d in body] == [existing, missing]
    assert body[0]["available"] is True
    assert body[1]["available"] is False


async def test_admin_forbidden_for_other_hall_and_unknown_user(client, admin_headers, db_session):
    headers, _hall_id = admin_headers

    other_hall = Hall(name="Зал №2")
    outsider = User(
        login="petr",
        password_hash=hash_password("ppass"),
        full_name="Пётр",
        role=UserRole.eater,
    )
    db_session.add_all([other_hall, outsider])
    await db_session.flush()
    db_session.add(UserHall(user_id=outsider.id, hall_id=other_hall.id))
    await db_session.commit()

    day = (dt.date.today() + dt.timedelta(days=DAY_OFFSET)).isoformat()
    r = await client.get(
        f"/api/v1/admin/users/{outsider.id}/calendar?from={day}&to={day}", headers=headers
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "forbidden"

    r = await client.get(
        f"/api/v1/admin/users/{uuid.uuid4()}/calendar?from={day}&to={day}", headers=headers
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "user_not_found"


async def test_admin_calendar_range_validation(client, admin_headers):
    headers, hall_id = admin_headers
    user_id = await _eater_id(client, headers, hall_id)

    r = await client.get(
        f"/api/v1/admin/users/{user_id}/calendar?from=2026-11-05&to=2026-11-01",
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_range"

    r = await client.get(
        f"/api/v1/admin/users/{user_id}/calendar?from=2026-01-01&to=2026-06-01",
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "range_too_large"
