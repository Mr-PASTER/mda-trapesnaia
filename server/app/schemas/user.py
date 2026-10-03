import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    login: str
    full_name: str
    role: UserRole
    is_active: bool
    default_meal_type_id: uuid.UUID | None


class HallBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class MeOut(UserOut):
    halls: list[HallBrief] = []
