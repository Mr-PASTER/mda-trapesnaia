import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind, RuleKind


class ScheduleRule(Base):
    __tablename__ = "schedule_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[RuleKind] = mapped_column(Enum(RuleKind, name="rule_kind"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScheduleRuleWeekday(Base):
    __tablename__ = "schedule_rule_weekdays"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)  # 0=Mon .. 6=Sun


class ScheduleRuleDate(Base):
    __tablename__ = "schedule_rule_dates"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    specific_date: Mapped[date] = mapped_column(Date, primary_key=True)


class ScheduleRuleMeal(Base):
    __tablename__ = "schedule_rule_meals"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    meal_kind: Mapped[MealKind] = mapped_column(
        Enum(MealKind, name="meal_kind"), primary_key=True
    )


class ScheduleRuleHall(Base):
    __tablename__ = "schedule_rule_halls"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
