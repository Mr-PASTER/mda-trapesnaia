from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.integrations.ldap.config import DEFAULT_LOGIN_FILTER, LdapSettings

REQUIRED: dict[str, Any] = {
    "enabled": True,
    "host": "dc.example.org",
    "base_dn": "ou=people,dc=example,dc=org",
    "bind_dn": "cn=svc,ou=service,dc=example,dc=org",
    "bind_password": "secret",
}


def make_settings(**overrides: Any) -> LdapSettings:
    data = dict(REQUIRED)
    data.update(overrides)
    return LdapSettings(**data)


def test_safe_defaults() -> None:
    settings = LdapSettings()

    assert settings.enabled is False
    assert settings.tls == "none"
    assert settings.tls_verify is True
    assert settings.login_filter == DEFAULT_LOGIN_FILTER
    assert settings.name_attr == "cn"
    assert settings.id_attr == "entryUUID"
    assert settings.login_attr == "uid"
    assert settings.timeout == 5.0
    assert settings.sync_enabled is False
    assert settings.sync_hour == 23


def test_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("LDAP_ENABLED", "true")
    monkeypatch.setenv("LDAP_HOST", "ldaps://dc.example.org:1636")
    monkeypatch.setenv("LDAP_BASE_DN", "ou=people,dc=example,dc=org")
    monkeypatch.setenv("LDAP_BIND_DN", "cn=svc,ou=service,dc=example,dc=org")
    monkeypatch.setenv("LDAP_BIND_PASSWORD", "secret")
    monkeypatch.setenv("LDAP_TLS", "LDAPS")
    monkeypatch.setenv("LDAP_TIMEOUT", "7")

    settings = LdapSettings()

    assert settings.enabled is True
    assert settings.tls == "ldaps"
    assert settings.timeout == 7.0
    assert settings.endpoint().port == 1636


def test_reads_dotenv_file(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LDAP_ENABLED=true",
                "LDAP_HOST=dc.example.org:1389",
                "LDAP_BASE_DN=ou=people,dc=example,dc=org",
                "LDAP_BIND_DN=cn=svc,ou=service,dc=example,dc=org",
                "LDAP_BIND_PASSWORD=secret",
                "LDAP_USER_FILTER=(memberOf=cn=trapeznaya,ou=groups,dc=example,dc=org)",
            ]
        ),
        encoding="utf-8",
    )

    settings = LdapSettings()

    assert settings.enabled is True
    assert settings.user_filter is not None
    assert settings.user_filter.startswith("(memberOf=")
    assert settings.endpoint().port == 1389


def test_blank_optional_values_become_none() -> None:
    settings = LdapSettings(
        host="   ",
        user_filter=" ",
        tls_ca_cert="",
    )

    assert settings.host is None
    assert settings.user_filter is None
    assert settings.tls_ca_cert is None


def test_empty_bind_password_is_missing() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_settings(bind_password="")

    assert "LDAP_BIND_PASSWORD" in str(exc_info.value)


def test_required_settings_are_checked_when_enabled() -> None:
    with pytest.raises(ValidationError) as exc_info:
        LdapSettings(enabled=True)

    message = str(exc_info.value)
    assert "LDAP_HOST" in message
    assert "LDAP_BASE_DN" in message
    assert "LDAP_BIND_DN" in message
    assert "LDAP_BIND_PASSWORD" in message


def test_required_settings_are_not_checked_when_disabled() -> None:
    settings = LdapSettings(enabled=False)

    assert settings.host is None


def test_login_filter_must_have_placeholder() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_settings(login_filter="(uid=static)")

    assert "{login}" in str(exc_info.value)


def test_percent_uid_placeholder_is_accepted() -> None:
    settings = make_settings(
        login_filter="(&(objectClass=posixAccount)(uid=%uid))"
    )

    assert "%uid" in settings.login_filter


@pytest.mark.parametrize(
    ("host", "tls", "expected"),
    [
        ("dc.example.org", "none", ("dc.example.org", 389, False)),
        ("dc.example.org:1389", "none", ("dc.example.org", 1389, False)),
        ("ldap://dc.example.org", "none", ("dc.example.org", 389, False)),
        ("ldaps://dc.example.org", "none", ("dc.example.org", 636, True)),
        ("dc.example.org", "ldaps", ("dc.example.org", 636, True)),
        ("[::1]:1636", "ldaps", ("::1", 1636, True)),
        ("dc.example.org", "starttls", ("dc.example.org", 389, False)),
    ],
)
def test_endpoint_parsing(
    host: str,
    tls: str,
    expected: tuple[str, int, bool],
) -> None:
    settings = make_settings(host=host, tls=tls)
    endpoint = settings.endpoint()

    assert (endpoint.host, endpoint.port, endpoint.use_ssl) == expected


def test_starttls_conflicts_with_ldaps() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_settings(host="ldaps://dc.example.org", tls="starttls")

    assert "starttls" in str(exc_info.value)


def test_unsupported_host_scheme_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_settings(host="https://dc.example.org")

    assert "схема" in str(exc_info.value)


@pytest.mark.parametrize("hour", [-1, 24])
def test_sync_hour_range(hour: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(sync_hour=hour)


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        make_settings(timeout=0)


def test_import_filter_prefers_sync_filter() -> None:
    settings = make_settings(
        sync_filter="(objectClass=person)", user_filter="(memberOf=cn=a,dc=b)"
    )

    assert settings.import_filter() == "(objectClass=person)"


def test_import_filter_falls_back_to_user_filter() -> None:
    settings = make_settings(user_filter="(memberOf=cn=a,dc=b)")

    assert settings.import_filter() == "(memberOf=cn=a,dc=b)"


def test_import_filter_is_empty_without_filters() -> None:
    assert make_settings().import_filter() == ""
