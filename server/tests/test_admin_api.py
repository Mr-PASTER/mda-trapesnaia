import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import Hall, User, UserHall, UserRole

FP = "dev-1"


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
    await db_session.commit()
    r = await client.post(
        "/api/v1/auth/login",
        json={"login": "adm", "password": "apass"},
        headers={"X-Device-Fingerprint": FP},
    )
    return {
        "Authorization": f"Bearer {r.json()['token']}",
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
    future = (dt.date.today() + dt.timedelta(days=30)).isoformat()

    r = await client.put(
        f"/api/v1/admin/requests/{user_id}/{future}",
        headers=headers,
        json={"meals": {"breakfast": True}, "version": None},
    )
    assert r.status_code == 200
    assert r.json()["has_request"] is True
