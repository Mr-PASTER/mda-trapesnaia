import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_requests_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    meal_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meal_types.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RequestItem(Base):
    __tablename__ = "request_items"
    __table_args__ = (
        UniqueConstraint("request_id", "meal_kind", name="uq_request_items_request_meal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE")
    )
    meal_kind: Mapped[MealKind] = mapped_column(Enum(MealKind, name="meal_kind"))
    is_going: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reserve: Mapped[bool] = mapped_column(Boolean, default=False)
