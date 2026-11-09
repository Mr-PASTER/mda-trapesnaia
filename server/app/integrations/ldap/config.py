"""Настройки LDAP-модуля: читаются из переменных окружения и файла ``.env``."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import ClassVar, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LOGIN_FILTER = "(|(uid={login})(sAMAccountName={login}))"
LOGIN_PLACEHOLDERS = ("{login}", "%uid")

TlsMode = Literal["none", "starttls", "ldaps"]

_REQUIRED_WHEN_ENABLED = {
    "host": "LDAP_HOST",
    "base_dn": "LDAP_BASE_DN",
    "bind_dn": "LDAP_BIND_DN",
    "bind_password": "LDAP_BIND_PASSWORD",
}


@dataclass(frozen=True)
class LdapEndpoint:
    """Разобранный `LDAP_HOST`: куда подключаться и нужен ли LDAPS."""

    host: str
    port: int
    use_ssl: bool


class LdapSettings(BaseSettings):
    """Конфигурация LDAP из окружения с префиксом ``LDAP_``."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LDAP_",
        extra="ignore",
    )

    enabled: bool = False

    host: str | None = None
    version: int = 3
    base_dn: str | None = None
    bind_dn: str | None = None
    bind_password: str | None = None

    tls: TlsMode = "none"
    tls_verify: bool = True
    tls_ca_cert: str | None = None

    login_filter: str = DEFAULT_LOGIN_FILTER
    login_attr: str = "uid"
    name_attr: str = "cn"
    id_attr: str = "entryUUID"
    user_filter: str | None = None
    sync_filter: str | None = None

    timeout: float = Field(default=5.0, gt=0)

    sync_enabled: bool = False
    sync_hour: int = Field(default=23, ge=0, le=23)

    @field_validator("tls", mode="before")
    @classmethod
    def _normalize_tls(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator(
        "host",
        "base_dn",
        "bind_dn",
        "user_filter",
        "sync_filter",
        "tls_ca_cert",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("bind_password", mode="before")
    @classmethod
    def _empty_password_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value == "":
            return None
        return value

    @model_validator(mode="after")
    def _validate_enabled_config(self) -> LdapSettings:
        if not self.enabled:
            return self

        missing = [
            env_name
            for field_name, env_name in _REQUIRED_WHEN_ENABLED.items()
            if not getattr(self, field_name)
        ]
        if missing:
            raise ValueError(
                "LDAP включён, но не заданы обязательные настройки: "
                + ", ".join(missing)
            )

        if not any(token in self.login_filter for token in LOGIN_PLACEHOLDERS):
            raise ValueError(
                "LDAP_LOGIN_FILTER должен содержать {login} (или %uid)"
            )

        # Проверяет корректность хоста и совместимость с LDAP_TLS.
        _ = self.endpoint()
        return self

    def endpoint(self) -> LdapEndpoint:
        """Разбирает ``LDAP_HOST`` в хост, порт и признак SSL."""
        if not self.host:
            raise ValueError("LDAP_HOST не задан")

        raw = self.host.strip()
        scheme: str | None = None
        if "://" in raw:
            scheme, raw = raw.split("://", 1)
            scheme = scheme.strip().lower()
            if scheme not in ("ldap", "ldaps"):
                raise ValueError(
                    f"LDAP_HOST: неподдерживаемая схема {scheme!r}; допустимы ldap:// и ldaps://"
                )
            if not raw:
                raise ValueError("LDAP_HOST: не указан хост")

        parts = urlsplit(f"//{raw}")
        host = parts.hostname
        if not host:
            raise ValueError(f"LDAP_HOST: не удалось разобрать хост {self.host!r}")

        use_ssl = scheme == "ldaps" or self.tls == "ldaps"
        if self.tls == "starttls" and use_ssl:
            raise ValueError(
                "LDAP_TLS=starttls несовместим с ldaps:// или LDAP_TLS=ldaps"
            )

        port = parts.port
        if port is None:
            port = 636 if use_ssl else 389

        return LdapEndpoint(host=host, port=port, use_ssl=use_ssl)

    def import_filter(self) -> str:
        """Фильтр импорта: ``LDAP_SYNC_FILTER``, иначе ``LDAP_USER_FILTER``."""
        return (self.sync_filter or self.user_filter or "").strip()


@lru_cache(maxsize=1)
def get_settings() -> LdapSettings:
    """Возвращает настройки из ``.env``/окружения (кешируется на процесс)."""
    return LdapSettings()


def load_settings(env_file: str | None = ".env") -> LdapSettings:
    """Загружает настройки из указанного env-файла.

    ``None`` — читать только переменные окружения, без файла.
    """
    if env_file is None:
        return LdapSettings()
    # _env_file есть в pydantic-settings, но не виден статическому анализу.
    return LdapSettings(_env_file=env_file)  # pyright: ignore[reportCallIssue]
