import uuid

from sqlalchemy import Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind


class UserMealDefault(Base):
    __tablename__ = "user_meal_defaults"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    meal_kind: Mapped[MealKind] = mapped_column(
        Enum(MealKind, name="meal_kind"), primary_key=True
    )
    is_going: Mapped[bool] = mapped_column(Boolean, default=False)
