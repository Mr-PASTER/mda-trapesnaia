import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "dev-1"


@pytest.fixture
async def operator_token(db_session):
    u = User(login="root", password_hash=hash_password("rootpass"),
             full_name="Root", role=UserRole.operator)
    db_session.add(u)
    await db_session.commit()
    return u


async def _login(client, login="root", password="rootpass"):
    r = await client.post("/api/v1/auth/login", json={"login": login, "password": password},
                          headers={"X-Device-Fingerprint": FP})
    assert r.status_code == 200
    return {"X-Device-Fingerprint": FP}


async def test_operator_crud_flow(client, operator_token):
    h = await _login(client)

    # создать зал
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=h)
    assert r.status_code == 201
    hall_id = r.json()["id"]

    # дубль зала → 409
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=h)
    assert r.status_code == 409

    # типы питания
    r = await client.post("/api/v1/operator/meal-types",
                          json={"name": "Мясо", "sort_order": 1}, headers=h)
    assert r.status_code == 201
    mt_id = r.json()["id"]

    # нельзя удалить последний активный тип → 400
    r = await client.delete(f"/api/v1/operator/meal-types/{mt_id}", headers=h)
    assert r.status_code == 400
    assert r.json()["detail"] == "last_meal_type"

    # создать питающегося без зала → 400
    r = await client.post("/api/v1/operator/users", headers=h, json={
        "login": "ivan", "password": "pass", "full_name": "Иван",
        "role": "eater", "hall_ids": [],
    })
    assert r.status_code == 400

    # корректный питающийся
    r = await client.post("/api/v1/operator/users", headers=h, json={
        "login": "ivan", "password": "pass", "full_name": "Иван",
        "role": "eater", "hall_ids": [hall_id], "default_meal_type_id": mt_id,
    })
    assert r.status_code == 201
    user_id = r.json()["id"]
    assert r.json()["hall_ids"] == [hall_id]

    # настройки
    r = await client.get("/api/v1/operator/settings", headers=h)
    assert r.status_code == 200
    r = await client.put("/api/v1/operator/settings", json={"generation_days": 21}, headers=h)
    assert r.status_code == 200 and r.json()["generation_days"] == 21

    # мягкое удаление
    r = await client.delete(f"/api/v1/operator/users/{user_id}", headers=h)
    assert r.status_code == 204


async def test_non_operator_forbidden(client, db_session):
    # питающийся не должен иметь доступ к операторским эндпоинтам
    u = User(login="eater1", password_hash=hash_password("p"),
             full_name="Е", role=UserRole.eater)
    db_session.add(u)
    await db_session.commit()
    h = await _login(client, "eater1", "p")
    r = await client.get("/api/v1/operator/halls", headers=h)
    assert r.status_code == 403
