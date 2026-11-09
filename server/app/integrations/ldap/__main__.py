"""CLI для проверки рукопожатия с LDAP: транспорт, bind, поиск, вход."""

from __future__ import annotations

import argparse
import getpass
import hmac
import logging
import os
import socket
import sys
import traceback
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from dotenv import dotenv_values
from ldap3.utils.log import (
    NETWORK,
    set_library_log_activation_level,
    set_library_log_detail_level,
    set_library_log_hide_sensitive_data,
)

from .client import Ldap3Connector, LdapAuthenticator, LdapUnavailable
from .config import LdapEndpoint, LdapSettings, load_settings

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_UNAVAILABLE = 3
EXIT_SERVICE_BIND = 4
EXIT_USER_NOT_FOUND = 5
EXIT_USER_BIND = 6


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ldap-auth-check",
        description=(
            "Проверяет рукопожатие с LDAP по этапам: TCP/TLS, bind сервисной "
            "учёткой, поиск пользователя и bind его учётными данными."
        ),
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Путь к env-файлу с LDAP_* (по умолчанию .env)",
    )
    parser.add_argument(
        "--login",
        help="Логин для поиска и проверки входа (без него проверяются только "
        "транспорт и сервисная учётка)",
    )
    parser.add_argument(
        "--password",
        help="Пароль для bind пользователя. Лучше не передавать: если логин "
        "задан, пароль будет запрошен интерактивно",
    )
    parser.add_argument(
        "--no-user-bind",
        action="store_true",
        help="Остановиться после поиска, не выполнять bind пользователя",
    )
    parser.add_argument(
        "--service-only",
        action="store_true",
        help="Проверить только транспорт и bind сервисной учёткой",
    )
    parser.add_argument(
        "--ask-bind-password",
        action="store_true",
        help="Запросить пароль сервисной учётки интерактивно и использовать "
        "его вместо значения из .env (нигде не сохраняется)",
    )
    parser.add_argument(
        "--login-filter",
        help="Переопределить LDAP_LOGIN_FILTER (должен содержать {login} или %%uid)",
    )
    parser.add_argument(
        "--user-filter",
        help="Переопределить LDAP_USER_FILTER; пустая строка — отключить",
    )
    parser.add_argument(
        "--bind-dn",
        help="Переопределить LDAP_BIND_DN на время проверки",
    )
    parser.add_argument(
        "--base-dn",
        help="Переопределить LDAP_BASE_DN на время проверки",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Переопределить LDAP_TIMEOUT на время проверки, секунды",
    )
    parser.add_argument(
        "--tls",
        choices=("none", "starttls", "ldaps"),
        help="Переопределить LDAP_TLS на время проверки (none | starttls | ldaps)",
    )
    parser.add_argument(
        "-v",
        "--debug",
        action="store_true",
        help="Подробная диагностика: DNS/TCP preflight, логи ldap3 и traceback",
    )
    return parser


def _configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not debug:
        return

    ldap_logger = logging.getLogger("ldap3")
    ldap_logger.setLevel(logging.DEBUG)
    ldap_logger.propagate = True
    set_library_log_activation_level(logging.DEBUG)
    set_library_log_detail_level(NETWORK)
    set_library_log_hide_sensitive_data(True)


def _text(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value)
    return str(value)


def _password_match_report(entered: str, configured: str | None) -> str:
    """Сравнивает пароли, не раскрывая их значения."""
    if configured is None:
        return "загруженный пароль отсутствует"
    if hmac.compare_digest(entered, configured):
        return f"совпадает с загруженным ({len(entered)} символов)"
    return (
        "НЕ совпадает с загруженным: "
        f"введено {len(entered)}, загружено {len(configured)} символов"
    )


def _password_source(env_file: str) -> str:
    """Откуда реально берётся LDAP_BIND_PASSWORD: env, .env или ниоткуда."""
    path = Path(env_file)
    file_value: str | None = None
    if path.is_file():
        file_value = dotenv_values(path, encoding="utf-8").get(
            "LDAP_BIND_PASSWORD"
        )

    env_value = os.environ.get("LDAP_BIND_PASSWORD")
    if env_value is not None:
        if file_value is not None and file_value != env_value:
            return f"переменная окружения (перекрывает {path.resolve()})"
        return "переменная окружения"
    if file_value:
        return f"файл {path.resolve()}"
    return "не найден в .env/окружении"


def _print_settings(
    settings: LdapSettings,
    endpoint: LdapEndpoint,
    env_file: str,
    password_source: str,
) -> None:
    transport = "ldaps" if endpoint.use_ssl else settings.tls
    env_path = Path(env_file).resolve()
    env_exists = Path(env_file).is_file()
    print("== Конфигурация ==")
    print(f"  Сервер:      {endpoint.host}:{endpoint.port}")
    print(f"  Транспорт:   {transport}")
    print(
        f"  Env-файл:    {env_path} "
        f"({'найден' if env_exists else 'НЕ НАЙДЕН'})"
    )
    print(f"  Base DN:     {settings.base_dn}")
    print(f"  Bind DN:     {settings.bind_dn}")
    if settings.bind_password:
        print(
            f"  Bind пароль: задан ({len(settings.bind_password)} символов), "
            f"источник: {password_source}"
        )
        if password_source.startswith("переменная окружения (перекрывает"):
            print(
                "  ВНИМАНИЕ:    пароль из окружения перекрывает значение в .env"
            )
        if any(ord(char) < 32 for char in settings.bind_password):
            print(
                "  ВНИМАНИЕ:    в пароле есть управляющие символы — "
                "проверьте экранирование в .env"
            )
    else:
        print("  Bind пароль: —")
    print(f"  ФИО атрибут: {settings.name_attr}")
    print(f"  ID атрибут:  {settings.id_attr}")
    print(f"  Login filter:{settings.login_filter}")
    print(f"  User filter: {settings.user_filter or '—'}")
    print(f"  Таймаут:     {settings.timeout:g} с")
    if not endpoint.use_ssl and settings.tls == "none":
        print("  ВНИМАНИЕ:    TLS отключён (LDAP_TLS=none)")
    print()


class _PreflightError(RuntimeError):
    """DNS или сырой TCP до каталога не работают."""


def _preflight(endpoint: LdapEndpoint, timeout: float) -> None:
    """Проверяет DNS и TCP отдельно от ldap3 — так причина видна точнее."""
    try:
        infos = socket.getaddrinfo(
            endpoint.host,
            endpoint.port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise _PreflightError(
            f"DNS: не удалось разрешить {endpoint.host}:{endpoint.port}: {exc}"
        ) from exc

    addresses: list[str] = []
    for info in infos:
        address = str(info[4][0])
        if address not in addresses:
            addresses.append(address)
    print(f"       DNS: {', '.join(addresses) if addresses else '—'}")

    try:
        with socket.create_connection(
            (endpoint.host, endpoint.port),
            timeout=timeout,
        ) as sock:
            peer = sock.getpeername()
    except OSError as exc:
        raise _PreflightError(
            f"TCP: {endpoint.host}:{endpoint.port} недоступен: {exc}"
        ) from exc

    print(f"       TCP: {peer[0]}:{peer[1]} доступен")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(bool(args.debug))

    interactive_password: str | None = None
    if args.ask_bind_password:
        configured_password: str | None = None
        try:
            configured_password = load_settings(args.env_file).bind_password
        except Exception:  # noqa: BLE001 — сравнение не должно мешать вводу
            configured_password = None

        try:
            interactive_password = getpass.getpass("Пароль сервисной учётки: ")
        except (EOFError, KeyboardInterrupt):
            print("\n[FAIL] пароль не введён", file=sys.stderr)
            return EXIT_USAGE
        if not interactive_password or not interactive_password.strip():
            print("\n[FAIL] пустой пароль не отправляется", file=sys.stderr)
            return EXIT_USAGE

        print(
            "[INFO] введённый пароль "
            + _password_match_report(interactive_password, configured_password)
        )

    try:
        if interactive_password is not None:
            # Временная подмена, чтобы прошла валидация обязательных полей.
            previous = os.environ.get("LDAP_BIND_PASSWORD")
            os.environ["LDAP_BIND_PASSWORD"] = interactive_password
            try:
                settings = load_settings(args.env_file)
            finally:
                if previous is None:
                    os.environ.pop("LDAP_BIND_PASSWORD", None)
                else:
                    os.environ["LDAP_BIND_PASSWORD"] = previous
            settings = settings.model_copy(
                update={"bind_password": interactive_password}
            )
        else:
            settings = load_settings(args.env_file)
        if args.timeout is not None:
            settings = settings.model_copy(update={"timeout": args.timeout})
        if args.tls is not None:
            settings = settings.model_copy(update={"tls": args.tls})
        if args.login_filter is not None:
            if not any(
                token in args.login_filter for token in ("{login}", "%uid")
            ):
                print(
                    "[FAIL] --login-filter должен содержать {login} или %uid",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            settings = settings.model_copy(
                update={"login_filter": args.login_filter}
            )
        if args.user_filter is not None:
            settings = settings.model_copy(
                update={"user_filter": args.user_filter or None}
            )
        if args.bind_dn is not None:
            settings = settings.model_copy(update={"bind_dn": args.bind_dn})
        if args.base_dn is not None:
            settings = settings.model_copy(update={"base_dn": args.base_dn})
    except Exception as exc:  # noqa: BLE001 — CLI должен показать любую ошибку конфига
        print(f"[FAIL] конфигурация: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not settings.enabled:
        print(
            "[FAIL] LDAP_ENABLED=false. Включите LDAP в .env, чтобы проверять "
            "рукопожатие.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        endpoint = settings.endpoint()
    except ValueError as exc:
        print(f"[FAIL] конфигурация: {exc}", file=sys.stderr)
        return EXIT_USAGE

    password_source = (
        "интерактивный ввод"
        if interactive_password is not None
        else _password_source(args.env_file)
    )
    _print_settings(settings, endpoint, args.env_file, password_source)
    if args.debug:
        try:
            ldap3_version = package_version("ldap3")
        except PackageNotFoundError:
            ldap3_version = "unknown"
        print(f"       Python {sys.version.split()[0]}, ldap3 {ldap3_version}")
        print()

    connector = Ldap3Connector(settings)

    print("[1/4] Транспорт (TCP/TLS) ...")
    try:
        _preflight(endpoint, settings.timeout)
    except _PreflightError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    try:
        connection = connector.connect()
    except LdapUnavailable as exc:
        print(f"[FAIL] транспорт: {exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_UNAVAILABLE
    print("[ OK ] соединение установлено")

    try:
        print("[2/4] Bind сервисной учёткой ...")
        if not settings.bind_dn or settings.bind_password is None:
            print("[FAIL] в конфигурации нет LDAP_BIND_DN/PASSWORD", file=sys.stderr)
            return EXIT_USAGE
        if not connection.bind(settings.bind_dn, settings.bind_password):
            details = connection.describe_last_error()
            print(
                "[FAIL] сервисная учётка не прошла bind: " + details,
                file=sys.stderr,
            )
            return EXIT_SERVICE_BIND
        print("[ OK ] сервисная учётка прошла bind")

        if args.service_only or not args.login:
            print("[SKIP] поиск и bind пользователя не запрошены")
            return EXIT_OK

        print(f"[3/4] Поиск пользователя {args.login!r} ...")
        if not settings.base_dn:
            print("[FAIL] в конфигурации нет LDAP_BASE_DN", file=sys.stderr)
            return EXIT_USAGE

        authenticator = LdapAuthenticator(settings, connector=connector)
        search_filter = authenticator.build_search_filter(args.login)
        print(f"       фильтр: {search_filter}")
        entries = connection.search(
            settings.base_dn,
            search_filter,
            [settings.name_attr, settings.id_attr],
            size_limit=2,
        )
        if not entries:
            print(
                "[FAIL] пользователь не найден (или не проходит LDAP_USER_FILTER)",
                file=sys.stderr,
            )
            return EXIT_USER_NOT_FOUND
        if len(entries) > 1:
            print(
                f"[FAIL] найдено {len(entries)} записей — вход был бы отклонён "
                "как неоднозначный",
                file=sys.stderr,
            )
            return EXIT_USER_NOT_FOUND

        entry = entries[0]
        print(f"[ OK ] найдена запись: {entry.dn}")
        print(f"       {settings.name_attr}: {_text(entry.attributes.get(settings.name_attr))}")
        print(f"       {settings.id_attr}: {_text(entry.attributes.get(settings.id_attr))}")

        if args.no_user_bind:
            print("[SKIP] bind пользователя отключён флагом --no-user-bind")
            return EXIT_OK

        password = args.password
        if password is None:
            try:
                password = getpass.getpass("Пароль пользователя: ")
            except (EOFError, KeyboardInterrupt):
                print("\n[FAIL] пароль не введён", file=sys.stderr)
                return EXIT_USAGE
        if not password or not password.strip():
            print("[FAIL] пустой пароль до LDAP не отправляется", file=sys.stderr)
            return EXIT_USAGE

        print(f"[4/4] Bind пользователя {entry.dn} ...")
        user_connection = connector.connect()
        try:
            bound = user_connection.bind(entry.dn, password)
            bind_details = None if bound else user_connection.describe_last_error()
        finally:
            user_connection.unbind()

        if not bound:
            print(
                "[FAIL] пользователь не прошёл bind: "
                + (bind_details or "причина не указана"),
                file=sys.stderr,
            )
            return EXIT_USER_BIND
        print("[ OK ] пользователь прошёл bind")

        print()
        print("Рукопожатие успешно: транспорт, сервисная учётка, поиск и вход.")
        return EXIT_OK
    except LdapUnavailable as exc:
        print(f"[FAIL] LDAP: {exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_UNAVAILABLE
    finally:
        connection.unbind()


if __name__ == "__main__":
    raise SystemExit(main())
