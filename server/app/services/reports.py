import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall, MealKind, MealType, User, UserHall, UserRole
from app.schemas.report import (
    DailyReportOut, HallPeriodReportOut, HallReportOut, MealReportOut,
    PeriodReportOut, TypeCountOut,
)
from app.services import day_view


class _Accumulator:
    def __init__(self, type_ids: list[uuid.UUID]) -> None:
        self.type_ids = type_ids
        self.by_type = {mk: {tid: 0 for tid in type_ids} for mk in MealKind}
        self.reserve = {mk: {tid: 0 for tid in type_ids} for mk in MealKind}
        self.total = {mk: 0 for mk in MealKind}
        self.reserve_total = {mk: 0 for mk in MealKind}

    def add(self, meal_kind: MealKind, type_id: uuid.UUID | None, is_reserve: bool) -> None:
        if type_id is None or type_id not in self.by_type[meal_kind]:
            return
        self.by_type[meal_kind][type_id] += 1
        self.total[meal_kind] += 1
        if is_reserve:
            self.reserve[meal_kind][type_id] += 1
            self.reserve_total[meal_kind] += 1


async def _active_types(db: AsyncSession) -> list[MealType]:
    stmt = (
        select(MealType)
        .where(MealType.is_active.is_(True))
        .order_by(MealType.sort_order, MealType.name)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _halls(db: AsyncSession, hall_id: uuid.UUID | None) -> list[Hall]:
    stmt = select(Hall).where(Hall.is_active.is_(True)).order_by(Hall.name)
    if hall_id is not None:
        stmt = stmt.where(Hall.id == hall_id)
    return list((await db.execute(stmt)).scalars().all())


async def _eaters(db: AsyncSession, hall_id: uuid.UUID) -> list[User]:
    stmt = (
        select(User)
        .join(UserHall, UserHall.user_id == User.id)
        .where(User.role == UserRole.eater, User.is_active.is_(True), UserHall.hall_id == hall_id)
        .order_by(User.login)
    )
    return list((await db.execute(stmt)).scalars().all())


def _iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


async def _accumulate(
    db: AsyncSession, eaters: list[User], dates: list[date],
    types: list[MealType], fallback_id: uuid.UUID | None, acc: _Accumulator,
) -> None:
    for eater in eaters:
        for day_date in dates:
            state = await day_view.get_day_state(db, user=eater, day_date=day_date)
            type_id = state.meal_type_id or fallback_id
            for item in state.items:
                if not item.is_served or not item.is_going:
                    continue
                acc.add(item.meal_kind, type_id, item.is_reserve)


def _meal_reports(types: list[MealType], acc: _Accumulator) -> list[MealReportOut]:
    meals: list[MealReportOut] = []
    for mk in MealKind:
        by_type = [
            TypeCountOut(meal_type_id=t.id, name=t.name, count=acc.by_type[mk][t.id])
            for t in types
        ]
        reserve_by_type = [
            TypeCountOut(meal_type_id=t.id, name=t.name, count=acc.reserve[mk][t.id])
            for t in types
        ]
        meals.append(
            MealReportOut(
                meal_kind=mk, by_type=by_type, reserve_by_type=reserve_by_type,
                total=acc.total[mk], reserve_total=acc.reserve_total[mk],
            )
        )
    return meals


async def build_daily_report(
    db: AsyncSession, *, on_date: date, hall_id: uuid.UUID | None = None
) -> DailyReportOut:
    types = await _active_types(db)
    fallback_id = types[0].id if types else None
    type_ids = [t.id for t in types]

    halls_out: list[HallReportOut] = []
    grand_total = grand_reserve = 0

    for hall in await _halls(db, hall_id):
        acc = _Accumulator(type_ids)
        await _accumulate(db, await _eaters(db, hall.id), [on_date], types, fallback_id, acc)
        meals = _meal_reports(types, acc)
        day_total = sum(m.total for m in meals)
        day_reserve = sum(m.reserve_total for m in meals)
        grand_total += day_total
        grand_reserve += day_reserve
        halls_out.append(
            HallReportOut(hall_id=hall.id, hall_name=hall.name, meals=meals,
                          day_total=day_total, day_reserve_total=day_reserve)
        )

    return DailyReportOut(
        date=on_date, halls=halls_out,
        grand_total=grand_total, grand_reserve_total=grand_reserve,
    )


async def build_period_report(
    db: AsyncSession, *, start: date, end: date, hall_id: uuid.UUID | None = None
) -> PeriodReportOut:
    types = await _active_types(db)
    fallback_id = types[0].id if types else None
    type_ids = [t.id for t in types]
    dates = list(_iter_dates(start, end)) if end >= start else []

    halls_out: list[HallPeriodReportOut] = []
    grand_total = grand_reserve = 0

    for hall in await _halls(db, hall_id):
        acc = _Accumulator(type_ids)
        await _accumulate(db, await _eaters(db, hall.id), dates, types, fallback_id, acc)
        meals = _meal_reports(types, acc)
        period_total = sum(m.total for m in meals)
        period_reserve = sum(m.reserve_total for m in meals)
        grand_total += period_total
        grand_reserve += period_reserve
        halls_out.append(
            HallPeriodReportOut(hall_id=hall.id, hall_name=hall.name, meals=meals,
                                period_total=period_total, period_reserve_total=period_reserve)
        )

    return PeriodReportOut(
        date_from=start, date_to=end, halls=halls_out,
        grand_total=grand_total, grand_reserve_total=grand_reserve,
    )
