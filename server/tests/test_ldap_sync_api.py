from types import SimpleNamespace

import pytest

from app.core.security import hash_password
from app.integrations.ldap import LdapIdentity, LdapUnavailable
from app.models import Hall, User, UserRole
from app.repositories import users as users_repo
from app.services import ldap as ldap_service

HEADERS = {"X-Device-Fingerprint": "dev-sync"}


def identity(**over):
    data = dict(
        uid="uid-1",
        dn="uid=ivan,ou=people,dc=example,dc=org",
        login="ivan",
        full_name="Иван Иванов",
    )
    data.update(over)
    return LdapIdentity(**data)


@pytest.fixture
async def op_headers(client, db_session):
    db_session.add(
        User(
            login="root", password_hash=hash_password("rootpass"),
            full_name="Root", role=UserRole.operator,
        )
    )
    await db_session.commit()
    r = await client.post(
        "/api/v1/auth/login",
        json={"login": "root", "password": "rootpass"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    return HEADERS


@pytest.fixture
async def hall(db_session):
    h = Hall(name="Зал А")
    db_session.add(h)
    await db_session.commit()
    return h


@pytest.fixture
def directory(monkeypatch):
    def install(identities=None, error=None, *, enabled=True,
                sync_filter="(objectClass=person)"):
        async def _list(search_filter):
            if error is not None:
                raise error
            return identities or []

        monkeypatch.setattr(ldap_service, "list_identities", _list)
        monkeypatch.setattr(
            ldap_service,
            "get_ldap_settings",
            lambda: SimpleNamespace(
                enabled=enabled,
                import_filter=lambda: sync_filter,
            ),
        )

    return install


async def test_sync_creates_people(client, op_headers, hall, directory):
    directory([
        identity(),
        identity(uid="uid-2", login="petr", full_name="Пётр"),
    ])

    r = await client.post("/api/v1/operator/users/ldap-sync", headers=op_headers)

    assert r.status_code == 200
    assert r.json() == {"created": 2, "updated": 0, "deactivated": 0, "skipped": 0}

    users = await client.get("/api/v1/operator/users?only_active=true", headers=op_headers)
    logins = {u["login"] for u in users.json()}
    assert {"ivan", "petr"} <= logins


async def test_sync_reports_updated_and_deactivated(client, op_headers, hall, directory):
    directory([identity()])
    await client.post("/api/v1/operator/users/ldap-sync", headers=op_headers)

    directory([identity(full_name="Иван Петров")])
    r = await client.post("/api/v1/operator/users/ldap-sync", headers=op_headers)

    assert r.json()["updated"] == 1

    directory([])
    r = await client.post("/api/v1/operator/users/ldap-sync", headers=op_headers)
    assert r.json()["deactivated"] == 1


async def test_sync_requires_filter(client, op_headers, directory):
    directory([identity()], sync_filter="")

    r = await client.post("/api/v1/operator/users/ldap-sync", headers=op_headers)

    assert r.status_code == 400
    assert r.json()["detail"] == "ldap_sync_filter_missing"


async def test_sync_requires_ldap_enabled(client, op_headers, directory):
    directory([identity()], enabled=False)

    r = await client.post("/api/v1/operator/users/ldap-sync", headers=op_headers)

    assert r.status_code == 400
    assert r.json()["detail"] == "ldap_disabled"


async def test_sync_reports_unavailable_catalog(client, op_headers, directory):
    directory(error=LdapUnavailable("down"))

    r = await client.post("/api/v1/operator/users/ldap-sync", headers=op_headers)

    assert r.status_code == 503
    assert r.json()["detail"] == "ldap_unavailable"


async def test_sync_forbidden_for_eater(client, db_session, directory):
    db_session.add(
        User(
            login="eater1", password_hash=hash_password("pass1234"),
            full_name="Е", role=UserRole.eater,
        )
    )
    await db_session.commit()
    await client.post(
        "/api/v1/auth/login",
        json={"login": "eater1", "password": "pass1234"},
        headers=HEADERS,
    )
    directory([identity()])

    r = await client.post("/api/v1/operator/users/ldap-sync", headers=HEADERS)

    assert r.status_code == 403
    assert await users_repo.get_by_login(db_session, "ivan") is None
