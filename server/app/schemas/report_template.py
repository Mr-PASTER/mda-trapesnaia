import uuid

from pydantic import BaseModel, Field


class TemplateGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    show_subtotal: bool = True
    hall_ids: list[uuid.UUID] = []


class TemplateTotalIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    all_halls: bool = False
    hall_ids: list[uuid.UUID] = []


class ReportTemplateIn(BaseModel):
    groups: list[TemplateGroupIn] = []
    totals: list[TemplateTotalIn] = []


class TemplateGroupOut(TemplateGroupIn):
    id: uuid.UUID


class TemplateTotalOut(TemplateTotalIn):
    id: uuid.UUID


class ReportTemplateOut(BaseModel):
    groups: list[TemplateGroupOut] = []
    totals: list[TemplateTotalOut] = []
