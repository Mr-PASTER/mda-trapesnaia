import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import MealKind, RuleKind


class ScheduleRuleCreate(BaseModel):
    kind: RuleKind
    meal_kinds: list[MealKind] = Field(min_length=1)
    hall_ids: list[uuid.UUID] = Field(min_length=1)
    weekdays: list[int] = []
    dates: list[date] = []


class ScheduleRuleUpdate(BaseModel):
    is_active: bool | None = None
    meal_kinds: list[MealKind] | None = None
    hall_ids: list[uuid.UUID] | None = None
    weekdays: list[int] | None = None
    dates: list[date] | None = None


class ScheduleRuleOut(BaseModel):
    id: uuid.UUID
    kind: RuleKind
    is_active: bool
    meal_kinds: list[MealKind]
    hall_ids: list[uuid.UUID]
    weekdays: list[int]
    dates: list[date]
