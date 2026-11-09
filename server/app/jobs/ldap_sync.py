import logging

from app.db.session import SessionLocal
from app.integrations.ldap import LdapUnavailable
from app.services import ldap_sync

logger = logging.getLogger(__name__)


async def run_ldap_sync() -> None:
    async with SessionLocal() as db:
        try:
            result = await ldap_sync.sync_directory(db)
        except ldap_sync.SyncFilterMissing as exc:
            logger.error("LDAP-синк не выполнен: %s", exc)
            await db.rollback()
            return
        except LdapUnavailable as exc:
            logger.warning("LDAP-синк пропущен, каталог недоступен: %s", exc)
            await db.rollback()
            return
        await db.commit()
    logger.info("LDAP-синк завершён: %s", result.summary())
