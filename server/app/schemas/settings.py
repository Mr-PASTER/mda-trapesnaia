from datetime import time

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdate(BaseModel):
    generation_days: int | None = Field(default=None, ge=1)
    deadline_offset_days: int | None = Field(default=None, ge=0)
    deadline_time: time | None = None


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_days: int
    deadline_offset_days: int
    deadline_time: time
