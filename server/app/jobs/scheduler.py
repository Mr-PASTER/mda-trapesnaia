from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.jobs.ldap_sync import run_ldap_sync
from app.jobs.maintenance import run_daily_maintenance
from app.services import ldap as ldap_service

_scheduler: AsyncIOScheduler | None = None


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        run_daily_maintenance,
        CronTrigger(hour=23, minute=59),
        id="daily_maintenance",
        replace_existing=True,
    )
    ldap_settings = ldap_service.get_ldap_settings()
    if ldap_settings.sync_enabled:
        scheduler.add_job(
            run_ldap_sync,
            CronTrigger(hour=ldap_settings.sync_hour, minute=59),
            id="ldap_sync",
            replace_existing=True,
        )
    return scheduler


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = create_scheduler()
        _scheduler.start()
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
