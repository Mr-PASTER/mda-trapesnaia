import uuid

from pydantic import BaseModel, ConfigDict, Field


class MealTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int = 0


class MealTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None
    is_active: bool | None = None


class MealTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    icon: str | None
    sort_order: int
    is_active: bool
