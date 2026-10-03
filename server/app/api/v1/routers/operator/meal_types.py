import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.meal_type import MealTypeIn, MealTypeOut, MealTypeUpdate
from app.services import meal_types

router = APIRouter(prefix="/meal-types", tags=["operator:meal-types"])
_guard = require_roles(UserRole.operator)


@router.get("", response_model=list[MealTypeOut])
async def list_meal_types(only_active: bool = True, db: AsyncSession = Depends(get_db),
                          _: User = Depends(_guard)):
    return await meal_types.list_meal_types(db, only_active=only_active)


@router.post("", response_model=MealTypeOut, status_code=status.HTTP_201_CREATED)
async def create_meal_type(payload: MealTypeIn, db: AsyncSession = Depends(get_db),
                           user: User = Depends(_guard)):
    try:
        mt = await meal_types.create_meal_type(
            db, actor_id=user.id, name=payload.name, sort_order=payload.sort_order
        )
    except meal_types.MealTypeAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    await db.commit()
    return mt


@router.put("/{meal_type_id}", response_model=MealTypeOut)
async def update_meal_type(meal_type_id: uuid.UUID, payload: MealTypeUpdate,
                           db: AsyncSession = Depends(get_db), user: User = Depends(_guard)):
    try:
        mt = await meal_types.update_meal_type(
            db, actor_id=user.id, meal_type_id=meal_type_id, name=payload.name,
            sort_order=payload.sort_order, is_active=payload.is_active,
        )
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="meal_type_not_found")
    except meal_types.MealTypeAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    except meal_types.LastMealType:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="last_meal_type")
    await db.commit()
    return mt


@router.delete("/{meal_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal_type(meal_type_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                           user: User = Depends(_guard)):
    try:
        await meal_types.deactivate_meal_type(db, actor_id=user.id, meal_type_id=meal_type_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="meal_type_not_found")
    except meal_types.LastMealType:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="last_meal_type")
    await db.commit()
