import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "device-1"


@pytest.fixture
async def operator(db_session):
    user = User(
        login="oper",
        password_hash=hash_password("secret123"),
        full_name="Оператор",
        role=UserRole.operator,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_login_me_logout_flow(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "oper", "password": "secret123"},
        headers={"X-Device-Fingerprint": FP},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" not in body
    assert body["login"] == "oper"
    assert body["role"] == "operator"
    assert "password_hash" not in body

    headers = {"X-Device-Fingerprint": FP}

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["login"] == "oper"

    out = await client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 204

    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401


async def test_login_bad_password(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "oper", "password": "nope"},
        headers={"X-Device-Fingerprint": FP},
    )
    assert resp.status_code == 401


async def test_fingerprint_change_revokes_session(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "oper", "password": "secret123"},
        headers={"X-Device-Fingerprint": FP},
    )
    assert resp.status_code == 200

    other = {"X-Device-Fingerprint": "device-2"}
    r1 = await client.get("/api/v1/auth/me", headers=other)
    assert r1.status_code == 401

    same = {"X-Device-Fingerprint": FP}
    r2 = await client.get("/api/v1/auth/me", headers=same)
    assert r2.status_code == 401  # сессия уже отозвана
