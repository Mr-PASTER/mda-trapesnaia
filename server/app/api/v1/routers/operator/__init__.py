from fastapi import APIRouter

from app.api.v1.routers.operator import (
    days,
    halls,
    logs,
    meal_types,
    schedule_rules,
    settings,
    users,
)

operator_router = APIRouter(prefix="/operator")
operator_router.include_router(halls.router)
operator_router.include_router(meal_types.router)
operator_router.include_router(users.router)
operator_router.include_router(settings.router)
operator_router.include_router(schedule_rules.router)
operator_router.include_router(days.router)
operator_router.include_router(logs.router)
