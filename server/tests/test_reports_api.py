import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import Hall, MealType, User, UserRole

FP = "dev-1"


@pytest.fixture
async def accountant_headers(client, db_session):
    u = User(login="buh", password_hash=hash_password("bpass"),
             full_name="Бух", role=UserRole.accountant)
    db_session.add(u)
    await db_session.commit()
    await client.post("/api/v1/auth/login", json={"login": "buh", "password": "bpass"},
                      headers={"X-Device-Fingerprint": FP})
    return {"X-Device-Fingerprint": FP}


@pytest.fixture
async def eater_headers(client, db_session):
    u = User(login="ivan", password_hash=hash_password("ipass"),
             full_name="Иван", role=UserRole.eater)
    db_session.add(u)
    await db_session.commit()
    await client.post("/api/v1/auth/login", json={"login": "ivan", "password": "ipass"},
                      headers={"X-Device-Fingerprint": FP})
    return {"X-Device-Fingerprint": FP}


async def test_daily_report_shape(client, accountant_headers, db_session):
    db_session.add_all([Hall(name="Зал №1"), MealType(name="Мясо", sort_order=1)])
    await db_session.commit()

    r = await client.get("/api/v1/accountant/report?date=2026-06-10", headers=accountant_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-06-10"
    assert len(body["halls"]) >= 1
    meal = body["halls"][0]["meals"][0]
    assert {"meal_kind", "by_type", "reserve_by_type", "total", "reserve_total"} <= set(meal)


async def test_period_report_shape(client, accountant_headers, db_session):
    r = await client.get(
        "/api/v1/accountant/report/period?from=2026-06-01&to=2026-06-03",
        headers=accountant_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["from"] == "2026-06-01" and body["to"] == "2026-06-03"
    assert "grand_total" in body


async def test_eater_forbidden(client, eater_headers):
    r = await client.get("/api/v1/accountant/report?date=2026-06-10", headers=eater_headers)
    assert r.status_code == 403
