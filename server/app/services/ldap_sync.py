from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import users as users_repo
from app.services import ldap as ldap_service
from app.services import ldap_users

logger = logging.getLogger(__name__)


class SyncFilterMissing(RuntimeError):
    """Не задан фильтр импорта — импортировать весь каталог запрещено."""


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    skipped: int = 0

    def summary(self) -> str:
        return (
            f"создано {self.created}, обновлено {self.updated}, "
            f"отключено {self.deactivated}, пропущено {self.skipped}"
        )


async def sync_directory(db: AsyncSession) -> SyncResult:
    """Полная сверка каталога и локальных LDAP-записей.

    :raises SyncFilterMissing: пустой `LDAP_SYNC_FILTER`/`LDAP_USER_FILTER`.
    :raises LdapUnavailable: каталог недоступен; изменений не применяем.
    """
    search_filter = ldap_service.get_ldap_settings().import_filter()
    if not search_filter:
        raise SyncFilterMissing(
            "LDAP_SYNC_FILTER и LDAP_USER_FILTER пусты — импорт всего каталога запрещён"
        )

    identities = await ldap_service.list_identities(search_filter)
    seen: set[str] = set()
    stats = SyncResult()

    for identity in identities:
        uid = identity.uid[:128]
        result = await ldap_users.upsert_ldap_user(db, identity, source="sync")
        seen.add(uid)
        if result.user is None:
            if result.skipped == "login_taken":
                stats.skipped += 1
            continue
        if result.created:
            stats.created += 1
        else:
            stats.updated += 1

    for user in await users_repo.list_ldap(db, only_active=True):
        if user.ldap_uid and user.ldap_uid not in seen:
            user.is_active = False
            stats.deactivated += 1

    await db.flush()
    logger.info("LDAP-синк: %s", stats.summary())
    return stats
