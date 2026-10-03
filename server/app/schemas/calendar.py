from datetime import date

from pydantic import BaseModel, Field


class RegenerateRequest(BaseModel):
    from_: date = Field(alias="from")
    to: date
