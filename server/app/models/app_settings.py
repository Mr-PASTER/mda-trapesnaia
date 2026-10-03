from datetime import datetime, time

from sqlalchemy import DateTime, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    generation_days: Mapped[int] = mapped_column(Integer, default=14)
    deadline_offset_days: Mapped[int] = mapped_column(Integer, default=2)
    deadline_time: Mapped[time] = mapped_column(Time, default=time(13, 0))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
