from app.core.security import hash_password
from app.models import Hall, User, UserRole

FP = "dev-1"


async def _login(client, db_session, role):
    user = User(
        login=f"u_{role.value}", password_hash=hash_password("pass"),
        full_name="U", role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await client.post(
        "/api/v1/auth/login",
        json={"login": user.login, "password": "pass"},
        headers={"X-Device-Fingerprint": FP},
    )
    return {"X-Device-Fingerprint": FP}


async def test_accountant_can_save_and_read(client, db_session):
    headers = await _login(client, db_session, UserRole.accountant)
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.commit()

    body = {
        "groups": [{"name": "Студенты", "show_subtotal": True, "hall_ids": [str(hall.id)]}],
        "totals": [{"name": "ИТОГО", "all_halls": True, "hall_ids": []}],
    }
    r = await client.put("/api/v1/report-template", json=body, headers=headers)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["groups"][0]["name"] == "Студенты"
    assert saved["groups"][0]["hall_ids"] == [str(hall.id)]
    assert saved["totals"][0]["all_halls"] is True

    r = await client.get("/api/v1/report-template", headers=headers)
    assert r.status_code == 200
    assert r.json()["groups"][0]["name"] == "Студенты"


async def test_operator_can_read(client, db_session):
    headers = await _login(client, db_session, UserRole.operator)
    r = await client.get("/api/v1/report-template", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"groups": [], "totals": []}


async def test_eater_cannot_read(client, db_session):
    headers = await _login(client, db_session, UserRole.eater)
    r = await client.get("/api/v1/report-template", headers=headers)
    assert r.status_code == 403


async def test_duplicate_hall_returns_400(client, db_session):
    headers = await _login(client, db_session, UserRole.accountant)
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.commit()
    body = {
        "groups": [
            {"name": "A", "show_subtotal": True, "hall_ids": [str(hall.id), str(hall.id)]}
        ],
        "totals": [],
    }
    r = await client.put("/api/v1/report-template", json=body, headers=headers)
    assert r.status_code == 400


async def test_catalog_halls_available_to_accountant(client, db_session):
    headers = await _login(client, db_session, UserRole.accountant)
    db_session.add_all([Hall(name="Зал №1"), Hall(name="Зал №2", is_active=False)])
    await db_session.commit()
    r = await client.get("/api/v1/catalog/halls", headers=headers)
    assert r.status_code == 200
    assert [h["name"] for h in r.json()] == ["Зал №1"]
