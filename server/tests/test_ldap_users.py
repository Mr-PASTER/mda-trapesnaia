import pytest

from app.integrations.ldap import LdapIdentity
from app.models import AuthSource, Hall, User, UserRole
from app.repositories import users as users_repo
from app.services import ldap_users, users


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
async def halls(db_session):
    hall_b = Hall(name="Зал Б")
    hall_a = Hall(name="Зал А")
    db_session.add_all([hall_b, hall_a])
    await db_session.commit()
    return {"a": hall_a, "b": hall_b}


async def test_creates_eater_in_first_active_hall(db_session, halls):
    result = await ldap_users.upsert_ldap_user(db_session, identity())

    user = result.user
    assert result.created is True
    assert user.login == "ivan"
    assert user.role == UserRole.eater
    assert user.auth_source == AuthSource.ldap
    assert user.password_hash is None
    assert user.ldap_uid == "uid-1"
    assert user.is_active is True
    assert await users_repo.hall_ids_of(db_session, user.id) == {halls["a"].id}


async def test_updates_name_and_dn_on_second_login(db_session, halls):
    first = await ldap_users.upsert_ldap_user(db_session, identity())
    second = await ldap_users.upsert_ldap_user(
        db_session,
        identity(full_name="Иван Петров", dn="uid=ivan,ou=new,dc=example,dc=org"),
    )

    assert second.created is False
    assert second.user.id == first.user.id
    assert second.user.full_name == "Иван Петров"
    assert second.user.ldap_dn == "uid=ivan,ou=new,dc=example,dc=org"


async def test_login_is_updated_when_free(db_session, halls):
    await ldap_users.upsert_ldap_user(db_session, identity())

    result = await ldap_users.upsert_ldap_user(db_session, identity(login="ivanov"))

    assert result.user.login == "ivanov"


async def test_login_is_kept_when_taken(db_session, halls):
    db_session.add(
        User(login="ivanov", password_hash="x", full_name="Другой", role=UserRole.eater)
    )
    await db_session.commit()
    await ldap_users.upsert_ldap_user(db_session, identity())

    result = await ldap_users.upsert_ldap_user(db_session, identity(login="ivanov"))

    assert result.user.login == "ivan"


async def test_inactive_ldap_user_is_not_reactivated(db_session, halls):
    created = await ldap_users.upsert_ldap_user(db_session, identity())
    created.user.is_active = False
    await db_session.flush()

    result = await ldap_users.upsert_ldap_user(db_session, identity())

    assert result.user is None
    assert result.skipped == "inactive"


async def test_local_login_is_never_taken_over(db_session, halls):
    local = User(
        login="ivan", password_hash="x", full_name="Локальный", role=UserRole.eater
    )
    db_session.add(local)
    await db_session.commit()

    result = await ldap_users.upsert_ldap_user(db_session, identity())

    assert result.user is None
    assert result.skipped == "login_taken"
    assert local.ldap_uid is None


async def test_ldap_user_found_by_login_gets_uid(db_session, halls):
    orphan = User(
        login="ivan",
        password_hash=None,
        full_name="Иван",
        role=UserRole.eater,
        auth_source=AuthSource.ldap,
    )
    db_session.add(orphan)
    await db_session.commit()

    result = await ldap_users.upsert_ldap_user(db_session, identity())

    assert result.user.id == orphan.id
    assert result.user.ldap_uid == "uid-1"


async def test_no_active_hall_is_an_error(db_session):
    db_session.add(Hall(name="Закрытый", is_active=False))
    await db_session.commit()

    with pytest.raises(ldap_users.NoHallAvailable):
        await ldap_users.upsert_ldap_user(db_session, identity())


async def test_password_change_is_rejected_for_ldap_user(db_session, halls):
    created = await ldap_users.upsert_ldap_user(db_session, identity())

    with pytest.raises(users.PasswordNotAllowed):
        await users.set_password(
            db_session,
            actor_id=created.user.id,
            user_id=created.user.id,
            password="newpass",
        )
