from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings


async def get(db: AsyncSession) -> AppSettings | None:
    return await db.get(AppSettings, 1)


async def ensure(db: AsyncSession) -> AppSettings:
    row = await db.get(AppSettings, 1)
    if row is None:
        row = AppSettings(id=1)
        db.add(row)
        await db.flush()
    return row
