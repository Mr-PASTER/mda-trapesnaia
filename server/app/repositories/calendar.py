import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Day, DayHallMeal, Hall


async def get_or_create_day(db: AsyncSession, day_date: dt.date) -> Day:
    day = (await db.execute(select(Day).where(Day.date == day_date))).scalar_one_or_none()
    if day is None:
        day = Day(date=day_date)
        db.add(day)
        await db.flush()
    return day


async def list_active_halls(db: AsyncSession) -> list[Hall]:
    stmt = select(Hall).where(Hall.is_active.is_(True)).order_by(Hall.name)
    return list((await db.execute(stmt)).scalars().all())


async def clear_day_meals(db: AsyncSession, day_id) -> None:
    await db.execute(delete(DayHallMeal).where(DayHallMeal.day_id == day_id))


async def add_day_meals(db: AsyncSession, rows: list[DayHallMeal]) -> None:
    if rows:
        db.add_all(rows)
        await db.flush()
