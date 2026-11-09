import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReportGroup, ReportGroupHall, ReportTotal, ReportTotalHall


async def list_groups(db: AsyncSession) -> list[ReportGroup]:
    stmt = select(ReportGroup).order_by(ReportGroup.sort_order, ReportGroup.name)
    return list((await db.execute(stmt)).scalars().all())


async def list_group_halls(db: AsyncSession) -> list[ReportGroupHall]:
    stmt = select(ReportGroupHall).order_by(ReportGroupHall.sort_order)
    return list((await db.execute(stmt)).scalars().all())


async def list_totals(db: AsyncSession) -> list[ReportTotal]:
    stmt = select(ReportTotal).order_by(ReportTotal.sort_order, ReportTotal.name)
    return list((await db.execute(stmt)).scalars().all())


async def list_total_halls(db: AsyncSession) -> list[ReportTotalHall]:
    stmt = select(ReportTotalHall).order_by(ReportTotalHall.sort_order)
    return list((await db.execute(stmt)).scalars().all())


async def clear(db: AsyncSession) -> None:
    await db.execute(delete(ReportTotalHall))
    await db.execute(delete(ReportTotal))
    await db.execute(delete(ReportGroupHall))
    await db.execute(delete(ReportGroup))
    await db.flush()


async def add_group(
    db: AsyncSession, name: str, sort_order: int, show_subtotal: bool
) -> ReportGroup:
    group = ReportGroup(name=name, sort_order=sort_order, show_subtotal=show_subtotal)
    db.add(group)
    await db.flush()
    return group


async def add_group_hall(
    db: AsyncSession, group_id: uuid.UUID, hall_id: uuid.UUID, sort_order: int
) -> None:
    db.add(ReportGroupHall(group_id=group_id, hall_id=hall_id, sort_order=sort_order))


async def add_total(
    db: AsyncSession, name: str, sort_order: int, all_halls: bool
) -> ReportTotal:
    total = ReportTotal(name=name, sort_order=sort_order, all_halls=all_halls)
    db.add(total)
    await db.flush()
    return total


async def add_total_hall(
    db: AsyncSession, total_id: uuid.UUID, hall_id: uuid.UUID, sort_order: int
) -> None:
    db.add(ReportTotalHall(total_id=total_id, hall_id=hall_id, sort_order=sort_order))
