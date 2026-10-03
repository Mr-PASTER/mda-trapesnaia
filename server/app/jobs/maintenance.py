from app.db.session import SessionLocal
from app.services import calendar


async def run_daily_maintenance() -> None:
    async with SessionLocal() as db:
        await calendar.regenerate_horizon(db)
        await db.commit()
