import pytest
from sqlalchemy.exc import IntegrityError

from app.models import AuthSource, User, UserRole


def _user(login: str, **over):
    data = dict(login=login, password_hash=None, full_name=login, role=UserRole.eater)
    data.update(over)
    return User(**data)


async def test_auth_source_defaults_to_local(db_session):
    user = _user("plain")
    db_session.add(user)
    await db_session.flush()

    assert user.auth_source == AuthSource.local


async def test_ldap_uid_is_unique_when_set(db_session):
    db_session.add_all([
        _user("a", auth_source=AuthSource.ldap, ldap_uid="uid-1"),
        _user("b", auth_source=AuthSource.ldap, ldap_uid="uid-1"),
    ])

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_null_ldap_uid_does_not_conflict(db_session):
    db_session.add_all([
        _user("a", auth_source=AuthSource.ldap),
        _user("b", auth_source=AuthSource.ldap),
    ])
    await db_session.flush()

    assert True
