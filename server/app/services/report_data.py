import uuid
from dataclasses import dataclass, field
from datetime import date

from app.models import MealKind
from app.schemas.report import DailyReportOut
from app.services.reports import PeriodMatrix

TypePair = tuple[uuid.UUID, str]
MealCounts = dict[MealKind, dict[uuid.UUID, tuple[int, int]]]
DayCounts = dict[uuid.UUID, MealCounts]


@dataclass
class ReportData:
    types: list[TypePair] = field(default_factory=list)
    dates: list[date] = field(default_factory=list)
    hall_names: dict[uuid.UUID, str] = field(default_factory=dict)
    counts: dict[date, DayCounts] = field(default_factory=dict)


def report_data_from_daily(report: DailyReportOut) -> ReportData:
    if not report.halls:
        return ReportData(dates=[report.date])
    types: list[TypePair] = [
        (t.meal_type_id, t.name) for t in report.halls[0].meals[0].by_type
        if t.meal_type_id is not None
    ]
    hall_names: dict[uuid.UUID, str] = {}
    counts: DayCounts = {}
    for hall in report.halls:
        hall_names[hall.hall_id] = hall.hall_name
        per_meal: MealCounts = {}
        for meal in hall.meals:
            totals = {t.meal_type_id: t.count for t in meal.by_type}
            reserves = {t.meal_type_id: t.count for t in meal.reserve_by_type}
            per_meal[meal.meal_kind] = {
                tid: (totals.get(tid, 0), reserves.get(tid, 0)) for tid, _ in types
            }
        counts[hall.hall_id] = per_meal
    return ReportData(
        types=types,
        dates=[report.date],
        hall_names=hall_names,
        counts={report.date: counts},
    )


def report_data_from_matrix(matrix: PeriodMatrix) -> ReportData:
    types: list[TypePair] = [(t.id, t.name) for t in matrix.types]
    hall_names = {hall.id: hall.name for hall in matrix.halls}
    counts: dict[date, DayCounts] = {}
    for day_date in matrix.dates:
        per_day: DayCounts = {}
        for hall_id, acc in matrix.counts[day_date].items():
            per_day[hall_id] = {
                meal: {
                    tid: (acc.by_type[meal].get(tid, 0), acc.reserve[meal].get(tid, 0))
                    for tid, _ in types
                }
                for meal in MealKind
            }
        counts[day_date] = per_day
    return ReportData(
        types=types,
        dates=list(matrix.dates),
        hall_names=hall_names,
        counts=counts,
    )
