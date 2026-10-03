from app.db.session import SessionLocal
from app.services import audit, calendar


async def run_daily_maintenance() -> None:
    async with SessionLocal() as db:
        await calendar.regenerate_horizon(db)
        await audit.cleanup_older_than(db, audit.today_reset_point())
        await db.commit()
