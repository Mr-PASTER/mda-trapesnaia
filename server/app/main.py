from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.jobs.maintenance import run_daily_maintenance
from app.jobs.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_daily_maintenance()   # догон генерации при старте
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Трапезная МДА API", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
