from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.jobs.maintenance import run_daily_maintenance
from app.jobs.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_daily_maintenance()   # догон генерации при старте
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Трапезная МДА API",
    version="0.1.0",
    lifespan=lifespan,
    # Схему API можно закрыть в проде: DOCS_ENABLED=false.
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
