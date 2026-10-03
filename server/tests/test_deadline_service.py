import datetime as dt
from datetime import time
from zoneinfo import ZoneInfo

from app.models import User, UserRole
from app.services import deadline, settings as settings_service


async def _actor(db_session):
    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_deadline_and_lock(db_session):
    actor = await _actor(db_session)
    await settings_service.update_settings(
        db_session, actor_id=actor.id, deadline_offset_days=3, deadline_time=time(13, 0)
    )
    day = dt.date(2026, 10, 10)
    tz = ZoneInfo("Europe/Moscow")

    assert await deadline.deadline_for(db_session, day) == dt.datetime(2026, 10, 7, 13, 0, tzinfo=tz)
    assert await deadline.is_locked(
        db_session, day, now=dt.datetime(2026, 10, 7, 12, 0, tzinfo=tz)
    ) is False
    assert await deadline.is_locked(
        db_session, day, now=dt.datetime(2026, 10, 7, 14, 0, tzinfo=tz)
    ) is True
