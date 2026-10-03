import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "dev-1"


@pytest.fixture
async def operator_headers(client, db_session):
    u = User(login="root", password_hash=hash_password("rootpass"),
             full_name="Root", role=UserRole.operator)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "root", "password": "rootpass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


async def test_logs_capture_actions(client, operator_headers):
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=operator_headers)
    assert r.status_code == 201

    r = await client.get("/api/v1/operator/logs", headers=operator_headers)
    assert r.status_code == 200
    actions = [(log["action"], log["entity_type"]) for log in r.json()]
    assert ("create", "hall") in actions


async def test_logs_forbidden_for_eater(client, db_session):
    u = User(login="ivan", password_hash=hash_password("p"), full_name="И", role=UserRole.eater)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "ivan", "password": "p"},
                          headers={"X-Device-Fingerprint": FP})
    headers = {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}
    assert (await client.get("/api/v1/operator/logs", headers=headers)).status_code == 403
