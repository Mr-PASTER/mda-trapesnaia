import pytest

from app.models import (
    Hall,
    ReportGroup,
    ReportGroupHall,
    ReportTotal,
)


async def test_group_hall_link_is_unique(db_session):
    hall = Hall(name="Зал №1")
    group = ReportGroup(name="Студенты", sort_order=1, show_subtotal=True)
    db_session.add_all([hall, group])
    await db_session.flush()
    db_session.add(ReportGroupHall(group_id=group.id, hall_id=hall.id, sort_order=0))
    await db_session.flush()
    db_session.add(ReportGroupHall(group_id=group.id, hall_id=hall.id, sort_order=1))
    with pytest.raises(Exception):
        await db_session.flush()


async def test_total_all_halls_flag(db_session):
    total = ReportTotal(name="ИТОГО", sort_order=0, all_halls=True)
    db_session.add(total)
    await db_session.flush()
    assert total.id is not None
    assert await db_session.get(ReportTotal, total.id) is not None
