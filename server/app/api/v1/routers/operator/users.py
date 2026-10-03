import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.repositories import users as users_repo
from app.schemas.operator_user import (
    HallsSet, OperatorUserCreate, OperatorUserOut, OperatorUserUpdate, PasswordSet,
)
from app.services import users

router = APIRouter(prefix="/users", tags=["operator:users"])
_guard = require_roles(UserRole.operator)


async def _to_out(db: AsyncSession, user: User) -> OperatorUserOut:
    halls = await users_repo.hall_ids_of(db, user.id)
    out = OperatorUserOut.model_validate(user)
    out.hall_ids = sorted(halls)
    return out


@router.get("", response_model=list[OperatorUserOut])
async def list_users(role: UserRole | None = None, hall_id: uuid.UUID | None = None,
                     only_active: bool = False, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    result = []
    for u in await users.list_users(db, role=role, hall_id=hall_id, only_active=only_active):
        result.append(await _to_out(db, u))
    return result


@router.post("", response_model=OperatorUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: OperatorUserCreate, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(_guard)):
    try:
        user = await users.create_user(
            db, actor_id=actor.id, login=payload.login, password=payload.password,
            full_name=payload.full_name, role=payload.role, hall_ids=payload.hall_ids,
            default_meal_type_id=payload.default_meal_type_id,
        )
    except users.LoginAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="login_exists")
    except users.InvalidHalls as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_halls: {e}")
    except users.DefaultMealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    return await _to_out(db, user)


@router.put("/{user_id}", response_model=OperatorUserOut)
async def update_user(user_id: uuid.UUID, payload: OperatorUserUpdate,
                      db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        user = await users.update_user(
            db, actor_id=actor.id, user_id=user_id, full_name=payload.full_name,
            role=payload.role, default_meal_type_id=payload.default_meal_type_id,
        )
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    except users.InvalidHalls as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_halls: {e}")
    except users.DefaultMealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    return await _to_out(db, user)


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(user_id: uuid.UUID, payload: PasswordSet,
                       db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        await users.set_password(db, actor_id=actor.id, user_id=user_id, password=payload.password)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await db.commit()


@router.put("/{user_id}/halls", response_model=OperatorUserOut)
async def set_halls(user_id: uuid.UUID, payload: HallsSet,
                    db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        await users.set_halls(db, actor_id=actor.id, user_id=user_id, hall_ids=payload.hall_ids)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    except users.InvalidHalls as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_halls: {e}")
    user = await users_repo.get_by_id(db, user_id)
    await db.commit()
    return await _to_out(db, user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, hard: bool = False,
                      db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        if hard:
            await users.hard_delete_user(db, actor_id=actor.id, user_id=user_id)
        else:
            await users.deactivate_user(db, actor_id=actor.id, user_id=user_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await db.commit()
