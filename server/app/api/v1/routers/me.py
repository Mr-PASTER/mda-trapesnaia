from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.request import (
    DayStateOut,
    DayUpdateRequest,
    DefaultsOut,
    DefaultsUpdate,
    MealStateOut,
)
from app.services import day_view, defaults, requests

router = APIRouter(prefix="/me", tags=["me"])


def _day_out(state: day_view.DayState) -> DayStateOut:
    return DayStateOut(
        date=state.date,
        meal_type_id=state.meal_type_id,
        items=[MealStateOut(**vars(i)) for i in state.items],
        version=state.version,
        has_request=state.has_request,
        deadline_at=state.deadline_at,
        editable=state.editable,
    )


async def _defaults_out(db: AsyncSession, user: User) -> DefaultsOut:
    d = await defaults.get_defaults(db, user)
    return DefaultsOut(default_meal_type_id=d.meal_type_id, meals=d.meals)


@router.get("/defaults", response_model=DefaultsOut)
async def get_defaults(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await _defaults_out(db, user)


@router.put("/defaults", response_model=DefaultsOut)
async def update_defaults(
    payload: DefaultsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        await defaults.update_defaults(
            db,
            actor_id=user.id,
            user=user,
            meal_type_id=payload.default_meal_type_id,
            meals=payload.meals,
        )
    except defaults.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    return await _defaults_out(db, user)


@router.get("/calendar", response_model=list[DayStateOut])
async def calendar(
    from_: date = Query(alias="from"),
    to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = []
    current = from_
    while current <= to:
        result.append(_day_out(await day_view.get_day_state(db, user=user, day_date=current)))
        current = current.fromordinal(current.toordinal() + 1)
    return result


@router.put("/days/{day_date}", response_model=DayStateOut)
async def save_day(
    day_date: date,
    payload: DayUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        await requests.save_day(
            db,
            actor=user,
            target=user,
            day_date=day_date,
            meal_type_id=payload.meal_type_id,
            meals=payload.meals,
            version=payload.version,
        )
    except requests.DayLocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="day_locked")
    except requests.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    except requests.VersionConflict:
        state = await day_view.get_day_state(db, user=user, day_date=day_date)
        return JSONResponse(
            status_code=409,
            content={
                "detail": "record_changed",
                "current": _day_out(state).model_dump(mode="json"),
            },
        )
    await db.commit()
    state = await day_view.get_day_state(db, user=user, day_date=day_date)
    return _day_out(state)
