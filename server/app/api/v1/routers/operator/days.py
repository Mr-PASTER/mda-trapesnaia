from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.calendar import RegenerateRequest
from app.services import calendar

router = APIRouter(prefix="/days", tags=["operator:days"])
_guard = require_roles(UserRole.operator)


@router.post("/regenerate", status_code=status.HTTP_204_NO_CONTENT)
async def regenerate(payload: RegenerateRequest, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    start: date = payload.from_
    end: date = payload.to
    await calendar.regenerate_range(db, start, end)
    await db.commit()
