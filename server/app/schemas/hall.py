import uuid

from pydantic import BaseModel, ConfigDict, Field


class HallIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class HallUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class HallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
