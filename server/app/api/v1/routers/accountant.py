import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.report import DailyReportOut, PeriodReportOut
from app.services import reports

router = APIRouter(prefix="/accountant", tags=["accountant"])
_guard = require_roles(UserRole.accountant, UserRole.operator)


@router.get("/report", response_model=DailyReportOut)
async def daily_report(on_date: date = Query(alias="date"),
                       hall_id: uuid.UUID | None = None,
                       db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    return await reports.build_daily_report(db, on_date=on_date, hall_id=hall_id)


@router.get("/report/period", response_model=PeriodReportOut)
async def period_report(from_: date = Query(alias="from"), to: date = Query(...),
                        hall_id: uuid.UUID | None = None,
                        db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    return await reports.build_period_report(db, start=from_, end=to, hall_id=hall_id)
