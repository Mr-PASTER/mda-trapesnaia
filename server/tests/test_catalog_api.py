import pytest

from app.core.security import hash_password
from app.models import MealType, User, UserRole

FP = "dev-1"


@pytest.fixture
async def eater_headers(client, db_session):
    user = User(
        login="ivan",
        password_hash=hash_password("pass"),
        full_name="Иван",
        role=UserRole.eater,
    )
    db_session.add(user)
    db_session.add_all(
        [
            MealType(name="Завтрак", icon="breakfast", sort_order=1),
            MealType(name="Обед", icon="lunch", sort_order=2),
            MealType(name="Отключённый", icon="old", sort_order=3, is_active=False),
        ]
    )
    await db_session.commit()
    await client.post(
        "/api/v1/auth/login",
        json={"login": "ivan", "password": "pass"},
        headers={"X-Device-Fingerprint": FP},
    )
    return {"X-Device-Fingerprint": FP}


async def test_catalog_lists_only_active_meal_types(client, eater_headers):
    r = await client.get("/api/v1/catalog/meal-types", headers=eater_headers)
    assert r.status_code == 200
    body = r.json()
    assert [m["name"] for m in body] == ["Завтрак", "Обед"]
    assert body[0]["icon"] == "breakfast"
    assert all(m["is_active"] is True for m in body)


async def test_catalog_requires_auth(client):
    r = await client.get(
        "/api/v1/catalog/meal-types", headers={"X-Device-Fingerprint": FP}
    )
    assert r.status_code == 401
