from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services import settings as svc

router = APIRouter(prefix="/settings", tags=["operator:settings"])
_guard = require_roles(UserRole.operator)


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    row = await svc.get_settings(db)
    await db.commit()
    return row


@router.put("", response_model=SettingsOut)
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db),
                          user: User = Depends(_guard)):
    row = await svc.update_settings(
        db, actor_id=user.id, generation_days=payload.generation_days,
        deadline_offset_days=payload.deadline_offset_days, deadline_time=payload.deadline_time,
    )
    await db.commit()
    return row
