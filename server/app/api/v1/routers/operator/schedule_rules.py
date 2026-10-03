import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.schedule_rule import ScheduleRuleCreate, ScheduleRuleOut, ScheduleRuleUpdate
from app.services import schedule_rules as svc

router = APIRouter(prefix="/schedule-rules", tags=["operator:schedule-rules"])
_guard = require_roles(UserRole.operator)


async def _to_out(db, rule) -> ScheduleRuleOut:
    return ScheduleRuleOut(
        id=rule.id, kind=rule.kind, is_active=rule.is_active,
        meal_kinds=await svc.get_meal_kinds(db, rule.id),
        hall_ids=await svc.get_hall_ids(db, rule.id),
        weekdays=[w.weekday for w in await svc.get_weekdays(db, rule.id)],
        dates=[d.specific_date for d in await svc.get_dates(db, rule.id)],
    )


@router.get("", response_model=list[ScheduleRuleOut])
async def list_rules(only_active: bool = True, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    return [await _to_out(db, r) for r in await svc.list_rules(db, only_active=only_active)]


@router.post("", response_model=ScheduleRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(payload: ScheduleRuleCreate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        rule = await svc.create_rule(
            db, actor_id=user.id, kind=payload.kind, meal_kinds=payload.meal_kinds,
            hall_ids=payload.hall_ids, weekdays=payload.weekdays, dates=payload.dates,
        )
    except svc.InvalidRule as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_rule: {e}")
    await db.commit()
    return await _to_out(db, rule)


@router.put("/{rule_id}", response_model=ScheduleRuleOut)
async def update_rule(rule_id: uuid.UUID, payload: ScheduleRuleUpdate,
                      db: AsyncSession = Depends(get_db), user: User = Depends(_guard)):
    try:
        rule = await svc.update_rule(
            db, actor_id=user.id, rule_id=rule_id, is_active=payload.is_active,
            meal_kinds=payload.meal_kinds, hall_ids=payload.hall_ids,
            weekdays=payload.weekdays, dates=payload.dates,
        )
    except svc.RuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rule_not_found")
    except svc.InvalidRule as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_rule: {e}")
    await db.commit()
    return await _to_out(db, rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        await svc.deactivate_rule(db, actor_id=user.id, rule_id=rule_id)
    except svc.RuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rule_not_found")
    await db.commit()
