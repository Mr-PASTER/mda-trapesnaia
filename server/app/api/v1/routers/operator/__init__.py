from fastapi import APIRouter

from app.api.v1.routers.operator import halls, meal_types, settings, users

operator_router = APIRouter(prefix="/operator")
operator_router.include_router(halls.router)
operator_router.include_router(meal_types.router)
operator_router.include_router(users.router)
operator_router.include_router(settings.router)
