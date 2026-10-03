import datetime as dt
from zoneinfo import ZoneInfo

from app.services import audit

TZ = ZoneInfo("Europe/Moscow")


async def test_cleanup_removes_old_logs_only(db_session):
    old = dt.datetime(2020, 1, 1, 12, 0, tzinfo=TZ)
    await audit.record(db_session, actor_id=None, action="a", entity_type="hall")
    # создаём «старый» лог вручную
    from app.repositories import audit as repo

    await repo.create(db_session, user_id=None, action="old", entity_type="hall",
                      entity_id=None, details=None)
    await db_session.flush()

    # помечаем первый лог старым
    logs = await audit.list_logs(db_session)
    for log in logs:
        if log.action == "old":
            log.created_at = old
    await db_session.flush()

    cutoff = dt.datetime.combine(dt.date.today(), dt.time.min, tzinfo=TZ)
    deleted = await audit.cleanup_older_than(db_session, cutoff)
    assert deleted == 1
    remaining = await audit.list_logs(db_session)
    assert all(log.action != "old" for log in remaining)
    assert any(log.action == "a" for log in remaining)


async def test_today_reset_point_is_midnight(db_session):
    now = dt.datetime(2026, 10, 3, 17, 30, tzinfo=TZ)
    assert audit.today_reset_point(now) == dt.datetime(2026, 10, 3, 0, 0, tzinfo=TZ)
