from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services import settings as settings_service


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


async def deadline_for(db: AsyncSession, day_date: date) -> datetime:
    cfg = await settings_service.get_settings(db)
    moment = datetime.combine(
        day_date - timedelta(days=cfg.deadline_offset_days), cfg.deadline_time
    )
    return moment.replace(tzinfo=_tz())


async def is_locked(db: AsyncSession, day_date: date, now: datetime | None = None) -> bool:
    now = now or datetime.now(_tz())
    return now >= await deadline_for(db, day_date)
