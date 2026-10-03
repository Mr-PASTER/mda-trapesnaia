import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MealKind


class TypeCountOut(BaseModel):
    meal_type_id: uuid.UUID | None
    name: str
    count: int


class MealReportOut(BaseModel):
    meal_kind: MealKind
    by_type: list[TypeCountOut]
    reserve_by_type: list[TypeCountOut]
    total: int
    reserve_total: int


class HallReportOut(BaseModel):
    hall_id: uuid.UUID
    hall_name: str
    meals: list[MealReportOut]
    day_total: int
    day_reserve_total: int


class DailyReportOut(BaseModel):
    date: date
    halls: list[HallReportOut]
    grand_total: int
    grand_reserve_total: int


class HallPeriodReportOut(BaseModel):
    hall_id: uuid.UUID
    hall_name: str
    meals: list[MealReportOut]
    period_total: int
    period_reserve_total: int


class PeriodReportOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")
    halls: list[HallPeriodReportOut]
    grand_total: int
    grand_reserve_total: int
