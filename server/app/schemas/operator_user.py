import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole
from app.schemas.user import UserOut


class OperatorUserCreate(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=4, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    hall_ids: list[uuid.UUID] = []
    default_meal_type_id: uuid.UUID | None = None


class OperatorUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    default_meal_type_id: uuid.UUID | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=4, max_length=128)


class HallsSet(BaseModel):
    hall_ids: list[uuid.UUID]


class OperatorUserOut(UserOut):
    model_config = ConfigDict(from_attributes=True)
    hall_ids: list[uuid.UUID] = []
