import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.audit_log import AuditLogOut
from app.services import audit

router = APIRouter(prefix="/logs", tags=["operator:logs"])
_guard = require_roles(UserRole.operator)


@router.get("", response_model=list[AuditLogOut])
async def list_logs(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_guard),
):
    return await audit.list_logs(db, since=from_, until=to, user_id=user_id, limit=limit)
