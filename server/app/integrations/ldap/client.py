"""Аутентификация в LDAP: bind сервисной учёткой, поиск, rebind пользователем."""

from __future__ import annotations

import asyncio
import logging
import ssl
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from ldap3 import NONE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.core.results import (
    RESULT_CONFIDENTIALITY_REQUIRED,
    RESULT_INAPPROPRIATE_AUTHENTICATION,
    RESULT_INSUFFICIENT_ACCESS_RIGHTS,
    RESULT_INVALID_CREDENTIALS,
    RESULT_INVALID_DN_SYNTAX,
    RESULT_NO_SUCH_OBJECT,
    RESULT_SIZE_LIMIT_EXCEEDED,
    RESULT_STRONGER_AUTH_REQUIRED,
    RESULT_SUCCESS,
    RESULT_UNWILLING_TO_PERFORM,
)
from ldap3.utils.conv import escape_filter_chars

from .config import LdapEndpoint, LdapSettings, get_settings

logger = logging.getLogger(__name__)


class LdapUnavailable(RuntimeError):
    """Каталог недоступен: сеть, таймаут, TLS или сбой сервисной учётки."""


@dataclass(frozen=True)
class LdapIdentity:
    """Подтверждённая каталогом учётная запись."""

    uid: str
    dn: str
    login: str
    full_name: str


@dataclass(frozen=True)
class DirectoryEntry:
    """Запись, найденная в каталоге."""

    dn: str
    attributes: Mapping[str, object]


class DirectoryConnection(Protocol):
    """Минимальный интерфейс соединения — подменяется фейком в тестах."""

    def bind(self, user: str, password: str) -> bool:
        """Выполняет bind; ``False`` — неверные учётные данные."""
        ...

    def search(
        self,
        base_dn: str,
        search_filter: str,
        attributes: Sequence[str],
        size_limit: int = 2,
    ) -> list[DirectoryEntry]:
        """Ищет записи под ``base_dn``."""
        ...

    def unbind(self) -> None:
        """Закрывает соединение."""
        ...

    def describe_last_error(self) -> str:
        """Возвращает детали и подсказку по последней ошибке LDAP."""
        ...


class DirectoryConnector(Protocol):
    """Фабрика соединений; в тестах подменяется фейком."""

    def connect(self) -> DirectoryConnection:
        """Открывает соединение (TLS уже согласован), но не выполняет bind."""
        ...


def _as_text(value: object) -> str:
    """Приводит значение атрибута LDAP к строке."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _as_text(item)
            if text:
                return text
        return ""
    return str(value)


def _connection_details(connection: Connection) -> str:
    """Собирает всё, что ldap3 знает о последней ошибке."""
    details: list[str] = []
    last_error = getattr(connection, "last_error", None)
    if last_error:
        details.append(str(last_error))

    result = getattr(connection, "result", None)
    if isinstance(result, dict):
        description = result.get("description")
        if description:
            details.append(f"result={description} ({result.get('result')})")
        message = result.get("message")
        if message:
            details.append(f"message={message}")

    server = getattr(connection, "server", None)
    current_address = getattr(server, "current_address", None) if server else None
    if current_address:
        details.append(f"address={current_address[4]}")

    return "; ".join(details) or "ldap3 не сообщил причину"


_BIND_HINTS: dict[object, str] = {
    RESULT_INVALID_CREDENTIALS: (
        "неверный пароль или bind DN. Проверьте полный DN служебной учётки: "
        "в AD это обычно CN=...,CN=Users,DC=..., в FreeIPA — "
        "uid=...,cn=users,cn=accounts,DC=..."
    ),
    RESULT_INVALID_DN_SYNTAX: "некорректный синтаксис bind DN (LDAP_BIND_DN)",
    RESULT_NO_SUCH_OBJECT: "bind DN не найден в дереве каталога",
    RESULT_STRONGER_AUTH_REQUIRED: (
        "сервер требует более сильную аутентификацию — включите TLS/StartTLS"
    ),
    RESULT_CONFIDENTIALITY_REQUIRED: (
        "сервер требует шифрование: LDAP_TLS=starttls или ldaps"
    ),
    RESULT_UNWILLING_TO_PERFORM: (
        "сервер запрещает simple bind без шифрования — обычно нужен LDAPS"
    ),
    RESULT_INAPPROPRIATE_AUTHENTICATION: (
        "сервер не принимает simple bind для этой учётной записи"
    ),
    RESULT_INSUFFICIENT_ACCESS_RIGHTS: "учётной записи не хватает прав",
}


def _describe_connection_error(connection: Connection) -> str:
    details = _connection_details(connection)
    result = getattr(connection, "result", None)
    if isinstance(result, dict):
        hint = _BIND_HINTS.get(result.get("result"))
        if hint:
            return f"{details} — {hint}"
    return details


class _Ldap3Connection:
    """Адаптер ``ldap3.Connection`` под :class:`DirectoryConnection`."""

    def __init__(self, server: Server, settings: LdapSettings) -> None:
        self._settings: LdapSettings = settings
        self._connection: Connection | None = None
        logger.debug(
            "LDAP: открываю %s:%s (use_ssl=%s, tls=%s, timeout=%s)",
            server.host,
            server.port,
            server.ssl,
            settings.tls,
            settings.timeout,
        )
        try:
            self._connection = Connection(
                server,
                user=None,
                password=None,
                version=settings.version,
                read_only=True,
                receive_timeout=settings.timeout,
                auto_bind=False,
                raise_exceptions=False,
            )
            # ldap3.Connection.open() возвращает None, а не bool: при ошибке он
            # бросает исключение, при успехе выставляет closed = False.
            self._connection.open()
            if self._connection.closed:
                raise LdapUnavailable(
                    "не удалось открыть соединение с LDAP: "
                    + _connection_details(self._connection)
                )
            logger.debug(
                "LDAP: сокет открыт, адрес %s",
                getattr(self._connection.server, "current_address", None),
            )

            if settings.tls == "starttls":
                logger.debug("LDAP: запускаю StartTLS")
                if not self._connection.start_tls():
                    raise LdapUnavailable(
                        "StartTLS не согласован: "
                        + _connection_details(self._connection)
                    )
                logger.debug("LDAP: TLS согласован")
        except LdapUnavailable:
            self._close_quietly()
            raise
        except LDAPException as exc:
            self._close_quietly()
            raise LdapUnavailable(f"ошибка соединения с LDAP: {exc}") from exc

    def bind(self, user: str, password: str) -> bool:
        if self._connection is None:
            raise LdapUnavailable("соединение с LDAP не открыто")
        logger.debug("LDAP: bind %s", user)
        try:
            # rebind выставляет user/password и выполняет bind; Connection.bind()
            # в ldap3 не принимает учётные данные.
            bound = bool(self._connection.rebind(user, password))
        except LDAPException as exc:
            raise LdapUnavailable(f"ошибка bind в LDAP: {exc}") from exc
        if not bound:
            logger.debug(
                "LDAP: bind отклонён: %s", _describe_connection_error(self._connection)
            )
        return bound

    def search(
        self,
        base_dn: str,
        search_filter: str,
        attributes: Sequence[str],
        size_limit: int = 2,
    ) -> list[DirectoryEntry]:
        if self._connection is None:
            raise LdapUnavailable("соединение с LDAP не открыто")
        logger.debug("LDAP: поиск base=%s filter=%s", base_dn, search_filter)
        try:
            self._connection.search(
                search_base=base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=list(attributes),
                size_limit=size_limit,
            )
        except LDAPException as exc:
            raise LdapUnavailable(f"ошибка поиска в LDAP: {exc}") from exc

        # ldap3 возвращает False и при успешном поиске без записей, поэтому
        # ориентируемся на код результата LDAP, а не на bool.
        result_code = self._connection.result.get("result")
        if result_code not in (RESULT_SUCCESS, RESULT_SIZE_LIMIT_EXCEEDED):
            description = self._connection.result.get("description")
            raise LdapUnavailable(
                f"поиск в LDAP завершился ошибкой: {description}"
            )

        logger.debug(
            "LDAP: результат поиска %s, записей: %d",
            self._connection.result.get("description"),
            len(self._connection.entries),
        )

        entries: list[DirectoryEntry] = []
        for entry in self._connection.entries:
            values: dict[str, object] = {}
            for name in attributes:
                attribute = entry[name]
                if attribute is not None:
                    values[name] = attribute.value
            entries.append(DirectoryEntry(dn=entry.entry_dn, attributes=values))
        return entries

    def unbind(self) -> None:
        self._close_quietly()

    def describe_last_error(self) -> str:
        if self._connection is None:
            return "соединение с LDAP не открыто"
        return _describe_connection_error(self._connection)

    def _close_quietly(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.unbind()
        except LDAPException:
            logger.debug("не удалось корректно закрыть соединение с LDAP")


class Ldap3Connector:
    """Боевой коннектор на ``ldap3``; соединения короткоживущие."""

    def __init__(self, settings: LdapSettings) -> None:
        self._settings: LdapSettings = settings

    def connect(self) -> DirectoryConnection:
        endpoint = self._settings.endpoint()
        logger.debug(
            "LDAP: endpoint %s:%s use_ssl=%s tls=%s verify=%s ca=%s",
            endpoint.host,
            endpoint.port,
            endpoint.use_ssl,
            self._settings.tls,
            self._settings.tls_verify,
            self._settings.tls_ca_cert or "—",
        )
        return _Ldap3Connection(self._build_server(endpoint), self._settings)

    def _build_server(self, endpoint: LdapEndpoint) -> Server:
        tls = None
        if endpoint.use_ssl or self._settings.tls == "starttls":
            tls = Tls(
                validate=(
                    ssl.CERT_REQUIRED
                    if self._settings.tls_verify
                    else ssl.CERT_NONE
                ),
                ca_certs_file=self._settings.tls_ca_cert or None,
            )
        return Server(
            endpoint.host,
            port=endpoint.port,
            use_ssl=endpoint.use_ssl,
            tls=tls,
            get_info=NONE,
            connect_timeout=self._settings.timeout,
        )


class LdapAuthenticator:
    """Проверяет логин и пароль живым bind'ом в каталоге."""

    def __init__(
        self,
        settings: LdapSettings | None = None,
        connector: DirectoryConnector | None = None,
    ) -> None:
        self._settings: LdapSettings = settings or get_settings()
        self._connector: DirectoryConnector = connector or Ldap3Connector(
            self._settings
        )

    async def authenticate(self, login: str, password: str) -> LdapIdentity | None:
        """Возвращает учётную запись или ``None`` при неверных данных.

        :raises LdapUnavailable: каталог недоступен или сервисная учётка
            не смогла выполнить bind.
        """
        if not self._settings.enabled:
            return None

        login = (login or "").strip()
        # Пустой пароль до каталога не доходит: иначе возможен
        # «неаутентифицированный bind».
        if not login or not password or not password.strip():
            return None

        return await asyncio.to_thread(self.authenticate_sync, login, password)

    def authenticate_sync(self, login: str, password: str) -> LdapIdentity | None:
        """Синхронная часть :meth:`authenticate` — выполняется в отдельном потоке."""
        search_filter = self.build_search_filter(login)
        entry = self._find_entry(search_filter)
        if entry is None:
            return None

        if not self._bind_user(entry.dn, password):
            return None

        uid = _as_text(entry.attributes.get(self._settings.id_attr)) or entry.dn
        full_name = (
            _as_text(entry.attributes.get(self._settings.name_attr)) or login
        )
        return LdapIdentity(
            uid=uid,
            dn=entry.dn,
            login=login.lower(),
            full_name=full_name,
        )

    def identity_from_entry(self, entry: DirectoryEntry) -> LdapIdentity | None:
        """Собирает учётную запись из записи каталога (для синка)."""
        login = _as_text(entry.attributes.get(self._settings.login_attr)).strip().lower()
        if not login:
            logger.warning(
                "LDAP: у записи %s нет атрибута %s — пропуск",
                entry.dn,
                self._settings.login_attr,
            )
            return None
        uid = _as_text(entry.attributes.get(self._settings.id_attr)) or entry.dn
        full_name = _as_text(entry.attributes.get(self._settings.name_attr)) or login
        return LdapIdentity(uid=uid, dn=entry.dn, login=login, full_name=full_name)

    def list_entries_sync(self, search_filter: str) -> list[DirectoryEntry]:
        """Ищет все записи под ``LDAP_BASE_DN`` сервисной учёткой."""
        base_dn = self._settings.base_dn
        bind_dn = self._settings.bind_dn
        bind_password = self._settings.bind_password
        if not base_dn or not bind_dn or bind_password is None:
            raise LdapUnavailable("LDAP настроен не полностью")

        connection = self._connector.connect()
        try:
            if not connection.bind(bind_dn, bind_password):
                raise LdapUnavailable("сервисная учётка LDAP не прошла bind")
            return connection.search(
                base_dn,
                search_filter,
                attributes=[
                    self._settings.login_attr,
                    self._settings.name_attr,
                    self._settings.id_attr,
                ],
                size_limit=0,
            )
        finally:
            connection.unbind()

    async def list_entries(self, search_filter: str) -> list[DirectoryEntry]:
        return await asyncio.to_thread(self.list_entries_sync, search_filter)

    def build_search_filter(self, login: str) -> str:
        """Собирает фильтр поиска, экранируя логин по RFC 4515.

        Поддерживаются оба плейсхолдера: ``{login}`` и ``%uid`` (стиль
        ldap.conf/FreeIPA).
        """
        escaped = escape_filter_chars(login)
        login_filter = self._settings.login_filter.replace(
            "{login}", escaped
        ).replace("%uid", escaped)
        user_filter = (self._settings.user_filter or "").strip()
        if user_filter:
            return f"(&{login_filter}{user_filter})"
        return login_filter

    def _find_entry(self, search_filter: str) -> DirectoryEntry | None:
        base_dn = self._settings.base_dn
        bind_dn = self._settings.bind_dn
        bind_password = self._settings.bind_password

        if not base_dn or not bind_dn or bind_password is None:
            raise LdapUnavailable("LDAP настроен не полностью")

        connection = self._connector.connect()
        try:
            if not connection.bind(bind_dn, bind_password):
                raise LdapUnavailable("сервисная учётка LDAP не прошла bind")
            entries = connection.search(
                base_dn,
                search_filter,
                attributes=[self._settings.name_attr, self._settings.id_attr],
                size_limit=2,
            )
        finally:
            connection.unbind()

        if not entries:
            return None
        if len(entries) > 1:
            logger.warning(
                "LDAP: по логину найдено %d записей, вход отклонён", len(entries)
            )
            return None
        return entries[0]

    def _bind_user(self, dn: str, password: str) -> bool:
        connection = self._connector.connect()
        try:
            return connection.bind(dn, password)
        finally:
            connection.unbind()


async def authenticate(
    login: str,
    password: str,
    settings: LdapSettings | None = None,
) -> LdapIdentity | None:
    """Удобная обёртка для разового вызова."""
    return await LdapAuthenticator(settings=settings).authenticate(login, password)
