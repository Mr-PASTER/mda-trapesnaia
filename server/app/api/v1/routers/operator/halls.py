import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.hall import HallIn, HallOut, HallUpdate
from app.services import halls

router = APIRouter(prefix="/halls", tags=["operator:halls"])

_guard = require_roles(UserRole.operator)


@router.get("", response_model=list[HallOut])
async def list_halls(only_active: bool = True, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    return await halls.list_halls(db, only_active=only_active)


@router.post("", response_model=HallOut, status_code=status.HTTP_201_CREATED)
async def create_hall(payload: HallIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        hall = await halls.create_hall(db, actor_id=user.id, name=payload.name)
    except halls.HallAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    await db.commit()
    return hall


@router.put("/{hall_id}", response_model=HallOut)
async def update_hall(hall_id: uuid.UUID, payload: HallUpdate,
                      db: AsyncSession = Depends(get_db), user: User = Depends(_guard)):
    try:
        hall = await halls.update_hall(
            db, actor_id=user.id, hall_id=hall_id,
            name=payload.name, is_active=payload.is_active,
        )
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="hall_not_found")
    except halls.HallAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    await db.commit()
    return hall


@router.delete("/{hall_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hall(hall_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        await halls.deactivate_hall(db, actor_id=user.id, hall_id=hall_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="hall_not_found")
    await db.commit()
