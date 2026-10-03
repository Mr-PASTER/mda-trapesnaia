import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import Hall, MealKind, MealType, User, UserHall, UserRole

FP = "dev-1"


@pytest.fixture
async def eater_headers(client, db_session):
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    user = User(
        login="ivan",
        password_hash=hash_password("pass"),
        full_name="Иван",
        role=UserRole.eater,
    )
    db_session.add_all([hall, mt, user])
    await db_session.flush()
    db_session.add(UserHall(user_id=user.id, hall_id=hall.id))
    user.default_meal_type_id = mt.id
    await db_session.commit()
    r = await client.post(
        "/api/v1/auth/login",
        json={"login": "ivan", "password": "pass"},
        headers={"X-Device-Fingerprint": FP},
    )
    return {"X-Device-Fingerprint": FP}


async def test_defaults_get_and_put(client, eater_headers):
    r = await client.get("/api/v1/me/defaults", headers=eater_headers)
    assert r.status_code == 200
    assert r.json()["default_meal_type_id"] is not None

    r = await client.put(
        "/api/v1/me/defaults",
        headers=eater_headers,
        json={
            "meals": {"breakfast": True, "lunch": True, "snack": False, "dinner": False},
        },
    )
    assert r.status_code == 200
    assert r.json()["meals"]["breakfast"] is True


async def test_save_day_lazy_request_and_lock(client, eater_headers):
    future = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    r = await client.put(
        f"/api/v1/me/days/{future}",
        headers=eater_headers,
        json={"meals": {"breakfast": True}, "version": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_request"] is True and body["version"] == 1

    # конфликт версий
    r = await client.put(
        f"/api/v1/me/days/{future}",
        headers=eater_headers,
        json={"meals": {"dinner": True}, "version": 999},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "record_changed"

    # прошлый день -> заблокировано
    past = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    r = await client.put(
        f"/api/v1/me/days/{past}", headers=eater_headers, json={"meals": {}}
    )
    assert r.status_code == 403
