from fastapi import FastAPI

from app.api.v1.router import api_router

app = FastAPI(title="Трапезная МДА API", version="0.1.0")
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
