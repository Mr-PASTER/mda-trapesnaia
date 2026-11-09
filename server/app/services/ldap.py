"""Точка доступа приложения к клиенту каталога.

Настройки и аутентификатор кешируются на процесс; тесты подменяют
``get_ldap_settings`` и ``get_authenticator``.
"""
from __future__ import annotations

from app.integrations.ldap import (
    LdapAuthenticator,
    LdapIdentity,
    LdapSettings,
    get_settings,
)

_authenticator: LdapAuthenticator | None = None


def get_ldap_settings() -> LdapSettings:
    return get_settings()


def get_authenticator() -> LdapAuthenticator:
    global _authenticator
    if _authenticator is None:
        _authenticator = LdapAuthenticator(get_ldap_settings())
    return _authenticator


def reset_cache() -> None:
    """Сбрасывает кеш — нужен после смены окружения."""
    global _authenticator
    _authenticator = None


async def authenticate(login: str, password: str) -> LdapIdentity | None:
    return await get_authenticator().authenticate(login, password)
