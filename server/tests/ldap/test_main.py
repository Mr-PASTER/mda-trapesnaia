from __future__ import annotations

from app.integrations.ldap.__main__ import (
    EXIT_SERVICE_BIND,
    EXIT_UNAVAILABLE,
    EXIT_USAGE,
    _password_match_report,
    _password_source,
    _print_settings,
    main,
)
from app.integrations.ldap.config import LdapSettings

ENABLED_ENV = {
    "LDAP_ENABLED": "true",
    "LDAP_HOST": "127.0.0.1:1",
    "LDAP_BASE_DN": "ou=people,dc=example,dc=org",
    "LDAP_BIND_DN": "cn=svc,ou=service,dc=example,dc=org",
    "LDAP_BIND_PASSWORD": "secret",
    "LDAP_TIMEOUT": "0.5",
}


def test_main_requires_enabled_config(capsys) -> None:
    code = main([])

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "LDAP_ENABLED=false" in captured.err


def test_main_reports_unreachable_host(monkeypatch, capsys) -> None:
    for name, value in ENABLED_ENV.items():
        monkeypatch.setenv(name, value)

    code = main([])

    captured = capsys.readouterr()
    assert code == EXIT_UNAVAILABLE
    assert "== Конфигурация ==" in captured.out
    assert "[FAIL] TCP:" in captured.err


def test_main_reports_service_bind_details(monkeypatch, capsys) -> None:
    for name, value in ENABLED_ENV.items():
        monkeypatch.setenv(name, value)

    monkeypatch.setattr(
        "app.integrations.ldap.__main__._preflight",
        lambda endpoint, timeout: None,
    )

    class FakeConnection:
        def bind(self, user: str, password: str) -> bool:
            return False

        def unbind(self) -> None:
            pass

        def describe_last_error(self) -> str:
            return "invalidCredentials (49) — неверный пароль или bind DN"

    class FakeConnector:
        def __init__(self, settings) -> None:
            pass

        def connect(self) -> FakeConnection:
            return FakeConnection()

    monkeypatch.setattr("app.integrations.ldap.__main__.Ldap3Connector", FakeConnector)

    code = main(["--service-only"])

    captured = capsys.readouterr()
    assert code == EXIT_SERVICE_BIND
    assert "invalidCredentials" in captured.err


def test_print_settings_shows_password_length_and_control_warning(capsys) -> None:
    settings = LdapSettings(
        enabled=False,
        host="dc.example.org",
        bind_password="line1\nline2",
    )

    _print_settings(
        settings,
        settings.endpoint(),
        ".env",
        "файл .env",
    )

    output = capsys.readouterr().out
    assert "(11 символов)" in output
    assert "управляющие символы" in output


def test_password_source_detects_environment_override(
    monkeypatch,
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LDAP_BIND_PASSWORD=from-file\n", encoding="utf-8")
    monkeypatch.setenv("LDAP_BIND_PASSWORD", "from-environment")

    source = _password_source(str(env_file))

    assert source.startswith("переменная окружения (перекрывает")


def test_password_source_detects_dotenv(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LDAP_BIND_PASSWORD=from-file\n", encoding="utf-8")

    source = _password_source(str(env_file))

    assert source.startswith("файл ")


def test_password_match_report_equal() -> None:
    assert _password_match_report("secret", "secret").startswith("совпадает")


def test_password_match_report_differs() -> None:
    report = _password_match_report("typed", "from-file")

    assert "НЕ совпадает" in report
    assert "введено 5" in report
    assert "загружено 9" in report


def test_password_match_report_missing() -> None:
    assert _password_match_report("typed", None) == "загруженный пароль отсутствует"


def test_filter_overrides(monkeypatch, capsys) -> None:
    for name, value in ENABLED_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        "app.integrations.ldap.__main__._preflight",
        lambda endpoint, timeout: None,
    )

    captured: dict[str, object] = {}

    class FakeConnection:
        def bind(self, user: str, password: str) -> bool:
            return True

        def unbind(self) -> None:
            pass

        def describe_last_error(self) -> str:
            return ""

    class FakeConnector:
        def __init__(self, settings) -> None:
            captured["settings"] = settings

        def connect(self) -> FakeConnection:
            return FakeConnection()

    monkeypatch.setattr("app.integrations.ldap.__main__.Ldap3Connector", FakeConnector)

    code = main(
        [
            "--service-only",
            "--login-filter",
            "(uid=%uid)",
            "--user-filter",
            "",
            "--bind-dn",
            "cn=admin,dc=mpda,dc=mda",
            "--base-dn",
            "dc=mpda,dc=mda",
        ]
    )

    assert code == 0
    settings = captured["settings"]
    assert getattr(settings, "login_filter") == "(uid=%uid)"
    assert getattr(settings, "user_filter") is None
    assert getattr(settings, "bind_dn") == "cn=admin,dc=mpda,dc=mda"
    assert getattr(settings, "base_dn") == "dc=mpda,dc=mda"


def test_tls_flag_overrides_environment(monkeypatch, capsys) -> None:
    for name, value in ENABLED_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("LDAP_TLS", "starttls")
    monkeypatch.setattr(
        "app.integrations.ldap.__main__._preflight",
        lambda endpoint, timeout: None,
    )

    captured: dict[str, object] = {}

    class FakeConnection:
        def bind(self, user: str, password: str) -> bool:
            return True

        def unbind(self) -> None:
            pass

        def describe_last_error(self) -> str:
            return ""

    class FakeConnector:
        def __init__(self, settings) -> None:
            captured["settings"] = settings

        def connect(self) -> FakeConnection:
            return FakeConnection()

    monkeypatch.setattr("app.integrations.ldap.__main__.Ldap3Connector", FakeConnector)

    code = main(["--service-only", "--tls", "none"])

    assert code == 0
    settings = captured["settings"]
    assert getattr(settings, "tls") == "none"
