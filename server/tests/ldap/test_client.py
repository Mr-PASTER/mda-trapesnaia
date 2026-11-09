from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pytest
from ldap3.core.results import (
    RESULT_INVALID_CREDENTIALS,
    RESULT_NO_SUCH_OBJECT,
    RESULT_SIZE_LIMIT_EXCEEDED,
    RESULT_SUCCESS,
)

from app.integrations.ldap.client import (
    DirectoryEntry,
    Ldap3Connector,
    LdapAuthenticator,
    LdapUnavailable,
    _Ldap3Connection,
    authenticate,
)
from app.integrations.ldap.config import LdapSettings

BIND_DN = "cn=svc,ou=service,dc=example,dc=org"
BIND_PASSWORD = "service-secret"
BASE_DN = "ou=people,dc=example,dc=org"
USER_DN = "uid=ivanov,ou=people,dc=example,dc=org"
USER_PASSWORD = "user-secret"


def make_settings(**overrides: Any) -> LdapSettings:
    data: dict[str, Any] = {
        "enabled": True,
        "host": "dc.example.org",
        "base_dn": BASE_DN,
        "bind_dn": BIND_DN,
        "bind_password": BIND_PASSWORD,
        "tls": "none",
        "timeout": 5.0,
    }
    data.update(overrides)
    return LdapSettings(**data)


def make_entry(**attributes: Any) -> DirectoryEntry:
    values: dict[str, object] = {"entryUUID": "uid-1", "cn": "Иванов Иван"}
    values.update(attributes)
    return DirectoryEntry(dn=USER_DN, attributes=values)


class FakeConnection:
    def __init__(self, connector: FakeConnector) -> None:
        self._connector = connector

    def bind(self, user: str, password: str) -> bool:
        connector = self._connector
        connector.bind_calls.append((user, password))
        if connector.bind_error is not None:
            raise connector.bind_error
        if user == connector.settings.bind_dn:
            return connector.service_bind_ok
        if connector.user_bind_error is not None:
            raise connector.user_bind_error
        if connector.user_bind_ok is not None:
            return connector.user_bind_ok
        return password == connector.user_password

    def search(
        self,
        base_dn: str,
        search_filter: str,
        attributes: Sequence[str],
        size_limit: int = 2,
    ) -> list[DirectoryEntry]:
        connector = self._connector
        connector.search_calls.append(
            (base_dn, search_filter, list(attributes), size_limit)
        )
        if connector.search_error is not None:
            raise connector.search_error
        return list(connector.entries)

    def unbind(self) -> None:
        self._connector.unbind_calls += 1

    def describe_last_error(self) -> str:
        return "fake: last error"


class FakeConnector:
    def __init__(
        self,
        settings: LdapSettings,
        *,
        entries: Sequence[DirectoryEntry] = (),
        service_bind_ok: bool = True,
        user_password: str | None = USER_PASSWORD,
        user_bind_ok: bool | None = None,
        user_bind_error: Exception | None = None,
        connect_error: Exception | None = None,
        bind_error: Exception | None = None,
        search_error: Exception | None = None,
    ) -> None:
        self.settings = settings
        self.entries = list(entries)
        self.service_bind_ok = service_bind_ok
        self.user_password = user_password
        self.user_bind_ok = user_bind_ok
        self.user_bind_error = user_bind_error
        self.connect_error = connect_error
        self.bind_error = bind_error
        self.search_error = search_error

        self.connect_calls = 0
        self.bind_calls: list[tuple[str, str]] = []
        self.search_calls: list[tuple[str, str, list[str], int]] = []
        self.unbind_calls = 0

    def connect(self) -> FakeConnection:
        self.connect_calls += 1
        if self.connect_error is not None:
            raise self.connect_error
        return FakeConnection(self)


def build(connector: FakeConnector, settings: LdapSettings | None = None):
    return LdapAuthenticator(settings or connector.settings, connector)


async def test_disabled_module_does_not_touch_directory() -> None:
    settings = make_settings(enabled=False)
    connector = FakeConnector(settings)
    result = await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert result is None
    assert connector.connect_calls == 0


@pytest.mark.parametrize("password", ["", "   "])
async def test_empty_password_does_not_reach_directory(password: str) -> None:
    settings = make_settings()
    connector = FakeConnector(settings, entries=[make_entry()])
    result = await build(connector).authenticate("ivanov", password)

    assert result is None
    assert connector.connect_calls == 0


async def test_empty_login_does_not_reach_directory() -> None:
    settings = make_settings()
    connector = FakeConnector(settings, entries=[make_entry()])
    result = await build(connector).authenticate("  ", USER_PASSWORD)

    assert result is None
    assert connector.connect_calls == 0


async def test_successful_authentication() -> None:
    settings = make_settings()
    connector = FakeConnector(settings, entries=[make_entry()])
    result = await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert result is not None
    assert result.uid == "uid-1"
    assert result.dn == USER_DN
    assert result.login == "ivanov"
    assert result.full_name == "Иванов Иван"

    assert connector.connect_calls == 2
    assert connector.bind_calls == [
        (BIND_DN, BIND_PASSWORD),
        (USER_DN, USER_PASSWORD),
    ]
    assert connector.unbind_calls == 2


async def test_login_is_lowercased_in_identity() -> None:
    settings = make_settings()
    connector = FakeConnector(settings, entries=[make_entry()])
    result = await build(connector).authenticate("Ivanov", USER_PASSWORD)

    assert result is not None
    assert result.login == "ivanov"


async def test_invalid_password_returns_none() -> None:
    settings = make_settings()
    connector = FakeConnector(settings, entries=[make_entry()])
    result = await build(connector).authenticate("ivanov", "wrong")

    assert result is None
    assert len(connector.bind_calls) == 2
    assert connector.unbind_calls == 2


async def test_unknown_login_returns_none_without_user_bind() -> None:
    settings = make_settings()
    connector = FakeConnector(settings, entries=[])
    result = await build(connector).authenticate("nobody", USER_PASSWORD)

    assert result is None
    assert connector.bind_calls == [(BIND_DN, BIND_PASSWORD)]


async def test_multiple_entries_are_rejected() -> None:
    settings = make_settings()
    connector = FakeConnector(
        settings,
        entries=[make_entry(), make_entry()],
    )
    result = await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert result is None
    assert connector.bind_calls == [(BIND_DN, BIND_PASSWORD)]


async def test_service_bind_failure_raises_unavailable() -> None:
    settings = make_settings()
    connector = FakeConnector(settings, service_bind_ok=False)

    with pytest.raises(LdapUnavailable):
        await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert connector.unbind_calls == 1


async def test_connect_error_raises_unavailable() -> None:
    settings = make_settings()
    connector = FakeConnector(
        settings,
        connect_error=LdapUnavailable("каталог недоступен"),
    )

    with pytest.raises(LdapUnavailable):
        await build(connector).authenticate("ivanov", USER_PASSWORD)


async def test_search_error_raises_unavailable() -> None:
    settings = make_settings()
    connector = FakeConnector(
        settings,
        entries=[make_entry()],
        search_error=LdapUnavailable("ошибка поиска"),
    )

    with pytest.raises(LdapUnavailable):
        await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert connector.unbind_calls == 1


async def test_user_bind_error_raises_unavailable() -> None:
    settings = make_settings()
    connector = FakeConnector(
        settings,
        entries=[make_entry()],
        user_bind_error=LdapUnavailable("соединение оборвалось"),
    )

    with pytest.raises(LdapUnavailable):
        await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert connector.unbind_calls == 2


async def test_login_is_escaped_in_search_filter() -> None:
    settings = make_settings()
    connector = FakeConnector(settings, entries=[])
    authenticator = build(connector)

    await authenticator.authenticate("*)(uid=*", USER_PASSWORD)

    assert connector.search_calls
    search_filter = connector.search_calls[0][1]
    assert r"\2a\29\28uid=\2a" in search_filter
    assert "*)(uid=*" not in search_filter


async def test_percent_uid_placeholder_is_substituted() -> None:
    settings = make_settings(
        login_filter=("(|(uid=%uid)(sAMAccountName=%uid))")
    )
    connector = FakeConnector(settings, entries=[])
    authenticator = build(connector)

    await authenticator.authenticate("ivanov", USER_PASSWORD)

    search_filter = connector.search_calls[0][1]
    assert "(uid=ivanov)" in search_filter
    assert "%uid" not in search_filter


async def test_freeipa_full_filter_is_substituted() -> None:
    full_filter = (
        "(&(&(|(objectclass=posixAccount))"
        "(|(memberof=cn=mdausers,cn=groups,dc=mpda,dc=mda)))(uid=%uid))"
    )
    settings = make_settings(login_filter=full_filter)
    connector = FakeConnector(settings, entries=[])
    authenticator = build(connector)

    await authenticator.authenticate("ivanov", USER_PASSWORD)

    assert connector.search_calls[0][1] == full_filter.replace(
        "%uid", "ivanov"
    )


async def test_freeipa_split_filter_is_combined() -> None:
    group_filter = (
        "(&(|(objectclass=posixAccount))"
        "(|(memberof=cn=mdausers,cn=groups,dc=mpda,dc=mda)))"
    )
    settings = make_settings(
        login_filter="(uid=%uid)",
        user_filter=group_filter,
    )
    connector = FakeConnector(settings, entries=[])
    authenticator = build(connector)

    await authenticator.authenticate("ivanov", USER_PASSWORD)

    assert connector.search_calls[0][1] == f"(&(uid=ivanov){group_filter})"


async def test_user_filter_is_appended() -> None:
    group = "(memberOf=cn=trapeznaya,ou=groups,dc=example,dc=org)"
    settings = make_settings(user_filter=group)
    connector = FakeConnector(settings, entries=[])
    authenticator = build(connector)

    await authenticator.authenticate("ivanov", USER_PASSWORD)

    search_filter = connector.search_calls[0][1]
    assert search_filter.startswith("(&")
    assert search_filter.endswith(f"{group})")
    assert "(uid=ivanov)" in search_filter


async def test_search_requests_configured_attributes() -> None:
    settings = make_settings(name_attr="displayName", id_attr="objectGUID")
    connector = FakeConnector(settings, entries=[])
    authenticator = build(connector)

    await authenticator.authenticate("ivanov", USER_PASSWORD)

    _, _, attributes, size_limit = connector.search_calls[0]
    assert attributes == ["displayName", "objectGUID"]
    assert size_limit == 2


async def test_missing_id_attribute_falls_back_to_dn() -> None:
    settings = make_settings()
    connector = FakeConnector(
        settings,
        entries=[DirectoryEntry(dn=USER_DN, attributes={"cn": "Иванов Иван"})],
    )
    result = await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert result is not None
    assert result.uid == USER_DN


async def test_missing_name_attribute_falls_back_to_login() -> None:
    settings = make_settings()
    connector = FakeConnector(
        settings,
        entries=[DirectoryEntry(dn=USER_DN, attributes={"entryUUID": "uid-1"})],
    )
    result = await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert result is not None
    assert result.full_name == "ivanov"


async def test_bytes_uid_is_converted_to_hex() -> None:
    settings = make_settings()
    connector = FakeConnector(
        settings,
        entries=[make_entry(entryUUID=b"\x01\x02\xab")],
    )
    result = await build(connector).authenticate("ivanov", USER_PASSWORD)

    assert result is not None
    assert result.uid == "0102ab"


async def test_module_level_authenticate_honours_disabled_flag() -> None:
    settings = make_settings(enabled=False)
    result = await authenticate("ivanov", USER_PASSWORD, settings=settings)

    assert result is None


class _FakeLdap3Entry:
    entry_dn = USER_DN

    def __getitem__(self, name: str):
        return None


class _FakeLdap3Backend:
    def __init__(self, result: dict[str, Any], entries: list[_FakeLdap3Entry]) -> None:
        self.result = result
        self.entries = entries
        self.search_kwargs: dict[str, Any] | None = None

    def search(self, **kwargs: Any) -> bool:
        self.search_kwargs = kwargs
        # ldap3 возвращает False, когда записей нет, даже при успехе.
        return bool(self.entries)


def make_ldap3_adapter(
    result_code: int,
    entries: list[_FakeLdap3Entry],
) -> tuple[_Ldap3Connection, _FakeLdap3Backend]:
    backend = _FakeLdap3Backend(
        {"result": result_code, "description": "test"},
        entries,
    )
    adapter = object.__new__(_Ldap3Connection)
    adapter._settings = make_settings()
    adapter._connection = cast(Any, backend)
    return adapter, backend


def test_ldap3_search_with_no_entries_is_not_an_error() -> None:
    adapter, _ = make_ldap3_adapter(RESULT_SUCCESS, [])

    entries = adapter.search(BASE_DN, "(uid=nobody)", ["cn", "entryUUID"])

    assert entries == []


def test_ldap3_search_error_raises_unavailable() -> None:
    adapter, _ = make_ldap3_adapter(RESULT_NO_SUCH_OBJECT, [])

    with pytest.raises(LdapUnavailable):
        adapter.search(BASE_DN, "(uid=ivanov)", ["cn", "entryUUID"])


def test_ldap3_size_limit_exceeded_still_returns_entries() -> None:
    adapter, backend = make_ldap3_adapter(
        RESULT_SIZE_LIMIT_EXCEEDED,
        [_FakeLdap3Entry(), _FakeLdap3Entry()],
    )

    entries = adapter.search(BASE_DN, "(uid=ivanov)", ["cn", "entryUUID"])

    assert len(entries) == 2
    assert backend.search_kwargs is not None
    assert backend.search_kwargs["size_limit"] == 2
    assert backend.search_kwargs["attributes"] == ["cn", "entryUUID"]


def test_connect_accepts_none_from_open(monkeypatch) -> None:
    class FakeLdap3Connection:
        def __init__(self, server, **kwargs: Any) -> None:
            self.server = server
            self.closed = True
            self.last_error: str | None = None
            self.result: dict[str, Any] = {}

        def open(self) -> None:
            self.closed = False
            # Настоящий ldap3.Connection.open() тоже возвращает None.
            return None

        def unbind(self) -> None:
            self.closed = True

    monkeypatch.setattr("app.integrations.ldap.client.Connection", FakeLdap3Connection)

    connection = Ldap3Connector(make_settings()).connect()
    connection.unbind()


def test_open_failure_reports_ldap3_details(monkeypatch) -> None:
    class FakeLdap3Connection:
        def __init__(self, server, **kwargs: Any) -> None:
            self.server = server
            self.closed = True
            self.last_error = "socket connection error while opening: boom"
            self.result: dict[str, Any] = {}

        def open(self) -> None:
            return None

        def unbind(self) -> None:
            self.closed = True

    monkeypatch.setattr("app.integrations.ldap.client.Connection", FakeLdap3Connection)

    with pytest.raises(LdapUnavailable) as exc_info:
        Ldap3Connector(make_settings()).connect()

    assert "boom" in str(exc_info.value)


class _FakeBindBackend:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.last_error: str | None = None
        self.server = None

    def rebind(self, user: str, password: str) -> bool:
        return False

    def unbind(self) -> None:
        pass


def test_bind_failure_describes_result_and_hint() -> None:
    adapter = object.__new__(_Ldap3Connection)
    adapter._settings = make_settings()
    adapter._connection = cast(
        Any,
        _FakeBindBackend(
            {
                "result": RESULT_INVALID_CREDENTIALS,
                "description": "invalidCredentials",
                "message": "Invalid credentials",
            }
        ),
    )

    assert adapter.bind("cn=admin,dc=mpda,dc=mda", "wrong") is False

    details = adapter.describe_last_error()
    assert "invalidCredentials" in details
    assert "message=Invalid credentials" in details
    assert "bind DN" in details
