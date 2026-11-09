from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ldap import LdapIdentity
from app.models import AuthSource, User, UserHall, UserRole
from app.repositories import halls as halls_repo
from app.repositories import users as users_repo

logger = logging.getLogger(__name__)


class NoHallAvailable(RuntimeError):
    """Активных залов нет — нового питающегося создать нельзя."""


@dataclass
class UpsertResult:
    user: User | None
    created: bool = False
    skipped: str | None = None  # "inactive" | "login_taken"


async def upsert_ldap_user(
    db: AsyncSession, identity: LdapIdentity, *, source: str = "login"
) -> UpsertResult:
    """Создаёт или обновляет локальную запись по данным каталога.

    ``skipped == "inactive"`` — запись отключена оператором, обратно не включаем.
    ``skipped == "login_taken"`` — логин занят локальной учёткой.
    """
    login = identity.login.strip().lower()
    uid = identity.uid[:128]
    dn = identity.dn[:512]
    full_name = (identity.full_name or login).strip()[:255] or login
    if not login:
        return UpsertResult(user=None, skipped="login_taken")

    user = await users_repo.get_by_ldap_uid(db, uid)
    if user is not None:
        if not user.is_active:
            logger.info("LDAP(%s): %s отключён локально — пропуск", source, login)
            return UpsertResult(user=None, skipped="inactive")
        user.full_name = full_name
        user.ldap_dn = dn
        if user.login != login:
            holder = await users_repo.get_by_login(db, login)
            if holder is None or holder.id == user.id:
                user.login = login
            else:
                logger.warning(
                    "LDAP(%s): новый логин %s занят — у %s оставлен %s",
                    source,
                    login,
                    uid,
                    user.login,
                )
        await db.flush()
        return UpsertResult(user=user)

    existing = await users_repo.get_by_login(db, login)
    if existing is not None:
        if existing.auth_source == AuthSource.local:
            logger.warning(
                "LDAP(%s): логин %s занят локальной учёткой — пропуск", source, login
            )
            return UpsertResult(user=None, skipped="login_taken")
        if not existing.is_active:
            logger.info("LDAP(%s): %s отключён локально — пропуск", source, login)
            return UpsertResult(user=None, skipped="inactive")
        existing.ldap_uid = uid
        existing.ldap_dn = dn
        existing.full_name = full_name
        await db.flush()
        return UpsertResult(user=existing)

    hall = await halls_repo.first_active(db)
    if hall is None:
        raise NoHallAvailable(login)

    user = User(
        login=login,
        password_hash=None,
        full_name=full_name,
        role=UserRole.eater,
        auth_source=AuthSource.ldap,
        ldap_uid=uid,
        ldap_dn=dn,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserHall(user_id=user.id, hall_id=hall.id))
    await db.flush()
    logger.info("LDAP(%s): создан %s (%s)", source, login, hall.name)
    return UpsertResult(user=user, created=True)
