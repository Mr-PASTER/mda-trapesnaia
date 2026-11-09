import pytest

from app.integrations.ldap import LdapIdentity, LdapUnavailable
from app.integrations.ldap.config import LdapSettings
from app.models import AuthSource, Hall, User, UserRole
from app.repositories import users as users_repo
from app.services import ldap as ldap_service
from app.services import ldap_sync


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
    return hall_a


@pytest.fixture
def directory(monkeypatch):
    def install(identities=None, error=None, sync_filter="(objectClass=person)"):
        async def _list(search_filter):
            _list.search_filter = search_filter
            if error is not None:
                raise error
            return identities or []

        _list.search_filter = None
        monkeypatch.setattr(ldap_service, "list_identities", _list)
        monkeypatch.setattr(
            ldap_service,
            "get_ldap_settings",
            lambda: LdapSettings(sync_filter=sync_filter),
        )
        return _list

    return install


async def test_creates_new_people(db_session, halls, directory):
    fake = directory(
        [identity(), identity(uid="uid-2", login="petr", full_name="Пётр")]
    )

    result = await ldap_sync.sync_directory(db_session)

    assert (result.created, result.updated, result.deactivated) == (2, 0, 0)
    assert fake.search_filter == "(objectClass=person)"
    assert len(await users_repo.list_ldap(db_session)) == 2


async def test_updates_full_name(db_session, halls, directory):
    directory([identity()])
    await ldap_sync.sync_directory(db_session)

    directory([identity(full_name="Иван Петров")])
    result = await ldap_sync.sync_directory(db_session)

    assert (result.created, result.updated) == (0, 1)
    user = await users_repo.get_by_login(db_session, "ivan")
    assert user.full_name == "Иван Петров"


async def test_renames_login_when_free(db_session, halls, directory):
    directory([identity()])
    await ldap_sync.sync_directory(db_session)

    directory([identity(login="ivanov")])
    await ldap_sync.sync_directory(db_session)

    assert await users_repo.get_by_login(db_session, "ivanov") is not None


async def test_missing_person_is_deactivated(db_session, halls, directory):
    directory([identity()])
    await ldap_sync.sync_directory(db_session)

    directory([])
    result = await ldap_sync.sync_directory(db_session)

    assert result.deactivated == 1
    user = await users_repo.get_by_login(db_session, "ivan")
    assert user.is_active is False


async def test_local_user_with_same_login_is_untouched(db_session, halls, directory):
    db_session.add(
        User(
            login="ivan",
            password_hash="x",
            full_name="Локальный",
            role=UserRole.eater,
        )
    )
    await db_session.commit()

    directory([identity()])
    result = await ldap_sync.sync_directory(db_session)

    assert result.skipped == 1
    user = await users_repo.get_by_login(db_session, "ivan")
    assert user.auth_source == AuthSource.local
    assert user.ldap_uid is None


async def test_disabled_person_stays_disabled(db_session, halls, directory):
    directory([identity()])
    await ldap_sync.sync_directory(db_session)
    user = await users_repo.get_by_login(db_session, "ivan")
    user.is_active = False
    await db_session.flush()

    directory([identity()])
    result = await ldap_sync.sync_directory(db_session)

    assert result.deactivated == 0
    assert (await users_repo.get_by_login(db_session, "ivan")).is_active is False


async def test_empty_filter_refuses_to_run(db_session, halls, directory):
    directory([identity()], sync_filter="")

    with pytest.raises(ldap_sync.SyncFilterMissing):
        await ldap_sync.sync_directory(db_session)


async def test_unavailable_directory_propagates(db_session, halls, directory):
    directory(error=LdapUnavailable("down"))

    with pytest.raises(LdapUnavailable):
        await ldap_sync.sync_directory(db_session)


async def test_sync_is_idempotent(db_session, halls, directory):
    directory([identity()])

    await ldap_sync.sync_directory(db_session)
    result = await ldap_sync.sync_directory(db_session)

    assert (result.created, result.updated) == (0, 1)
    assert len(await users_repo.list_ldap(db_session)) == 1
