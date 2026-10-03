import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "dev-1"


@pytest.fixture
async def op_headers(client, db_session):
    u = User(login="root", password_hash=hash_password("rootpass"),
             full_name="Root", role=UserRole.operator)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "root", "password": "rootpass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


async def test_create_rule_and_regenerate(client, op_headers):
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=op_headers)
    hall_id = r.json()["id"]

    r = await client.post("/api/v1/operator/schedule-rules", headers=op_headers, json={
        "kind": "recurring",
        "meal_kinds": ["breakfast"],
        "hall_ids": [hall_id],
        "weekdays": [6],
    })
    assert r.status_code == 201
    assert r.json()["weekdays"] == [6]

    sunday = dt.date(2026, 10, 4)
    r = await client.post("/api/v1/operator/days/regenerate", headers=op_headers,
                          json={"from": sunday.isoformat(), "to": sunday.isoformat()})
    assert r.status_code == 204


async def test_invalid_rule_returns_400(client, op_headers):
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=op_headers)
    hall_id = r.json()["id"]
    r = await client.post("/api/v1/operator/schedule-rules", headers=op_headers, json={
        "kind": "recurring", "meal_kinds": ["breakfast"], "hall_ids": [hall_id], "weekdays": [],
    })
    assert r.status_code == 400
