from fastapi import APIRouter

from app.api.v1.routers import admin, auth, me
from app.api.v1.routers.operator import operator_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(admin.router)
api_router.include_router(operator_router)
