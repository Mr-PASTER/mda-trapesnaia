from types import SimpleNamespace

import pytest

from app.core.security import hash_password
from app.integrations.ldap import LdapIdentity, LdapUnavailable
from app.models import AuthSource, Hall, User, UserRole
from app.services import auth, ldap as ldap_service

FP = "device-ldap"
HEADERS = {"X-Device-Fingerprint": FP}


def identity(**over):
    data = dict(
        uid="uid-1",
        dn="uid=ivan,ou=people,dc=example,dc=org",
        login="ivan",
        full_name="Иван Иванов",
    )
    data.update(over)
    return LdapIdentity(**data)


class FakeAuthenticator:
    def __init__(self, identity=None, error=None):
        self.identity = identity
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def authenticate(self, login, password):
        self.calls.append((login, password))
        if self.error is not None:
            raise self.error
        return self.identity


@pytest.fixture
def ldap(monkeypatch):
    def install(*, identity=None, error=None, enabled=True):
        fake = FakeAuthenticator(identity, error)
        monkeypatch.setattr(ldap_service, "get_authenticator", lambda: fake)
        monkeypatch.setattr(
            ldap_service,
            "get_ldap_settings",
            lambda: SimpleNamespace(enabled=enabled),
        )
        return fake

    return install


@pytest.fixture
async def halls(db_session):
    hall = Hall(name="Зал А")
    db_session.add(hall)
    await db_session.commit()
    return hall


async def test_first_login_creates_eater(db_session, halls, ldap):
    ldap(identity=identity())

    user = await auth.authenticate(db_session, "ivan", "secret")

    assert user is not None
    assert user.role == UserRole.eater
    assert user.auth_source == AuthSource.ldap
    assert user.full_name == "Иван Иванов"


async def test_second_login_updates_name(db_session, halls, ldap):
    ldap(identity=identity())
    await auth.authenticate(db_session, "ivan", "secret")

    ldap(identity=identity(full_name="Иван Петров"))
    user = await auth.authenticate(db_session, "ivan", "secret")

    assert user.full_name == "Иван Петров"


async def test_wrong_password_creates_nothing(db_session, halls, ldap):
    ldap(identity=None)

    assert await auth.authenticate(db_session, "ivan", "bad") is None
    assert await auth.authenticate(db_session, "nobody", "bad") is None


async def test_local_operator_does_not_touch_ldap(db_session, ldap):
    db_session.add(
        User(
            login="oper",
            password_hash=hash_password("secret123"),
            full_name="Оператор",
            role=UserRole.operator,
        )
    )
    await db_session.commit()
    fake = ldap(error=LdapUnavailable("down"))

    user = await auth.authenticate(db_session, "oper", "secret123")

    assert user is not None
    assert fake.calls == []


async def test_local_eater_is_not_hijacked(db_session, ldap):
    db_session.add(
        User(
            login="ivan",
            password_hash=hash_password("local123"),
            full_name="Локальный",
            role=UserRole.eater,
        )
    )
    await db_session.commit()
    fake = ldap(identity=identity())

    assert await auth.authenticate(db_session, "ivan", "local123") is not None
    assert await auth.authenticate(db_session, "ivan", "secret") is None
    assert fake.calls == []


async def test_disabled_local_user_is_rejected(db_session, ldap):
    db_session.add(
        User(
            login="off",
            password_hash=hash_password("pass1234"),
            full_name="Выкл",
            role=UserRole.eater,
            is_active=False,
        )
    )
    await db_session.commit()
    fake = ldap(identity=identity(login="off"))

    assert await auth.authenticate(db_session, "off", "pass1234") is None
    assert fake.calls == []


async def test_disabled_ldap_user_is_rejected_without_bind(db_session, halls, ldap):
    ldap(identity=identity())
    user = await auth.authenticate(db_session, "ivan", "secret")
    user.is_active = False
    await db_session.flush()

    fake = ldap(identity=identity())
    assert await auth.authenticate(db_session, "ivan", "secret") is None
    assert fake.calls == []


async def test_ldap_disabled_means_no_ldap_login(db_session, halls, ldap):
    fake = ldap(identity=identity(), enabled=False)

    assert await auth.authenticate(db_session, "ivan", "secret") is None
    assert fake.calls == []


async def test_api_login_success(client, halls, ldap):
    ldap(identity=identity())

    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "ivan", "password": "secret"},
        headers=HEADERS,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["login"] == "ivan"
    assert body["auth_source"] == "ldap"
    assert body["halls"] == [{"id": str(halls.id), "name": "Зал А"}]


async def test_api_login_invalid_credentials(client, halls, ldap):
    ldap(identity=None)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "ivan", "password": "bad"},
        headers=HEADERS,
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


async def test_api_login_ldap_unavailable(client, halls, ldap):
    ldap(error=LdapUnavailable("down"))

    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "ivan", "password": "secret"},
        headers=HEADERS,
    )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "ldap_unavailable"


async def test_api_login_no_hall(client, ldap):
    ldap(identity=identity())

    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "ivan", "password": "secret"},
        headers=HEADERS,
    )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "no_hall_available"
