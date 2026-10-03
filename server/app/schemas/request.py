import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import MealKind
from app.schemas.user import UserOut


class MealStateOut(BaseModel):
    meal_kind: MealKind
    is_served: bool
    is_going: bool
    is_reserve: bool


class DayStateOut(BaseModel):
    date: date
    meal_type_id: uuid.UUID | None
    items: list[MealStateOut]
    version: int | None
    has_request: bool
    deadline_at: datetime
    editable: bool


class DayUpdateRequest(BaseModel):
    meal_type_id: uuid.UUID | None = None
    meals: dict[MealKind, bool] = {}
    version: int | None = None


class DefaultsOut(BaseModel):
    default_meal_type_id: uuid.UUID | None
    meals: dict[MealKind, bool]


class DefaultsUpdate(BaseModel):
    default_meal_type_id: uuid.UUID | None = None
    meals: dict[MealKind, bool]


class AdminUserOut(UserOut):
    hall_ids: list[uuid.UUID] = []


class AdminDayOut(BaseModel):
    user: UserOut
    day: DayStateOut
