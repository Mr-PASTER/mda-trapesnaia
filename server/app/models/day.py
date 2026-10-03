import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind


class Day(Base):
    __tablename__ = "days"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DayHallMeal(Base):
    __tablename__ = "day_hall_meals"

    day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("days.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
    meal_kind: Mapped[MealKind] = mapped_column(
        Enum(MealKind, name="meal_kind"), primary_key=True
    )
    is_served: Mapped[bool] = mapped_column(Boolean, default=True)
