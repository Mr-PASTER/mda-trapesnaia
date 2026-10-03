import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.repositories import users as users_repo
from app.schemas.request import (
    AdminDayOut,
    AdminUserOut,
    DayStateOut,
    DayUpdateRequest,
    DefaultsOut,
    DefaultsUpdate,
    MealStateOut,
)
from app.services import access, day_view, defaults, requests

router = APIRouter(prefix="/admin", tags=["admin"])
_guard = require_roles(UserRole.admin, UserRole.operator)


def _day_out(state: day_view.DayState) -> DayStateOut:
    return DayStateOut(
        date=state.date,
        meal_type_id=state.meal_type_id,
        items=[MealStateOut(**vars(i)) for i in state.items],
        version=state.version,
        has_request=state.has_request,
        deadline_at=state.deadline_at,
        available=state.available,
        editable=state.editable,
    )


async def _assert_hall_access(db: AsyncSession, actor: User, hall_id: uuid.UUID | None) -> None:
    if actor.role == UserRole.operator:
        return
    if hall_id not in await access.hall_ids_of(db, actor.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="hall_forbidden")


async def _assert_read_access(db: AsyncSession, actor: User, target: User) -> None:
    # Operators may read any user; only admins are restricted to their halls.
    if actor.role != UserRole.admin:
        return
    try:
        await access.ensure_can_edit_user(db, actor=actor, target=target)
    except access.AccessDenied:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    hall_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_guard),
):
    if hall_id is not None:
        await _assert_hall_access(db, actor, hall_id)
    users = await users_repo.list_all(
        db, role=UserRole.eater, hall_id=hall_id, only_active=True
    )
    if hall_id is None and actor.role == UserRole.admin:
        allowed = await access.hall_ids_of(db, actor.id)
        users = [u for u in users if await users_repo.hall_ids_of(db, u.id) & allowed]
    out = []
    for u in users:
        o = AdminUserOut.model_validate(u)
        o.hall_ids = sorted(await users_repo.hall_ids_of(db, u.id))
        out.append(o)
    return out


@router.get("/requests", response_model=list[AdminDayOut])
async def requests_for_day(
    day_date: date,
    hall_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_guard),
):
    await _assert_hall_access(db, actor, hall_id)
    users = await users_repo.list_all(
        db, role=UserRole.eater, hall_id=hall_id, only_active=True
    )
    out = []
    for u in users:
        state = await day_view.get_day_state(db, user=u, day_date=day_date)
        out.append(AdminDayOut(user=u, day=_day_out(state)))
    return out


@router.put("/requests/{user_id}/{day_date}", response_model=DayStateOut)
async def save_for_user(
    user_id: uuid.UUID,
    day_date: date,
    payload: DayUpdateRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_guard),
):
    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    try:
        await requests.save_day(
            db,
            actor=actor,
            target=target,
            day_date=day_date,
            meal_type_id=payload.meal_type_id,
            meals=payload.meals,
            version=payload.version,
        )
    except access.AccessDenied:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    except requests.DayLocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="day_locked")
    except requests.DayNotAvailable:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="day_not_available")
    except requests.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    except requests.VersionConflict:
        state = await day_view.get_day_state(db, user=target, day_date=day_date)
        return JSONResponse(
            status_code=409,
            content={
                "detail": "record_changed",
                "current": _day_out(state).model_dump(mode="json"),
            },
        )
    await db.commit()
    state = await day_view.get_day_state(db, user=target, day_date=day_date)
    return _day_out(state)


@router.get("/users/{user_id}/defaults", response_model=DefaultsOut)
async def get_user_defaults(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_guard),
):
    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await _assert_read_access(db, actor, target)
    d = await defaults.get_defaults(db, target)
    return DefaultsOut(default_meal_type_id=d.meal_type_id, meals=d.meals)


@router.get("/users/{user_id}/calendar", response_model=list[DayStateOut])
async def get_user_calendar(
    user_id: uuid.UUID,
    from_: date = Query(alias="from"),
    to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_guard),
):
    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await _assert_read_access(db, actor, target)
    if to < from_:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_range")
    if (to - from_).days > 90:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="range_too_large")
    result = []
    current = from_
    while current <= to:
        result.append(_day_out(await day_view.get_day_state(db, user=target, day_date=current)))
        current = current.fromordinal(current.toordinal() + 1)
    return result


@router.put("/users/{user_id}/defaults")
async def update_user_defaults(
    user_id: uuid.UUID,
    payload: DefaultsUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_guard),
):
    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await access.ensure_can_edit_user(db, actor=actor, target=target)
    try:
        await defaults.update_defaults(
            db,
            actor_id=actor.id,
            user=target,
            meal_type_id=payload.default_meal_type_id,
            meals=payload.meals,
        )
    except access.AccessDenied:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    except defaults.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    d = await defaults.get_defaults(db, target)
    return {
        "default_meal_type_id": d.meal_type_id,
        "meals": {k.value: v for k, v in d.meals.items()},
    }
