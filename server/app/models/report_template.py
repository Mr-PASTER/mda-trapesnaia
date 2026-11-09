import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportGroup(Base):
    __tablename__ = "report_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    show_subtotal: Mapped[bool] = mapped_column(Boolean, default=True)


class ReportGroupHall(Base):
    __tablename__ = "report_group_halls"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_groups.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ReportTotal(Base):
    __tablename__ = "report_totals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    all_halls: Mapped[bool] = mapped_column(Boolean, default=False)


class ReportTotalHall(Base):
    __tablename__ = "report_total_halls"

    total_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_totals.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
