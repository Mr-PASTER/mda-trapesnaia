from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Hall, User
from app.repositories import meal_types as meal_types_repo
from app.schemas.meal_type import MealTypeOut
from app.schemas.user import HallBrief

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/meal-types", response_model=list[MealTypeOut])
async def list_meal_types(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[MealTypeOut]:
    return await meal_types_repo.list_all(db, only_active=True)


@router.get("/halls", response_model=list[HallBrief])
async def list_halls(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[HallBrief]:
    stmt = select(Hall).where(Hall.is_active.is_(True)).order_by(Hall.name)
    halls = (await db.execute(stmt)).scalars().all()
    return [HallBrief.model_validate(hall) for hall in halls]
