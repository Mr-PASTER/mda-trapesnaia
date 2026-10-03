import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AppSettings, MealType, User, UserRole

DEFAULT_MEAL_TYPES = ["Мясо", "Пост", "Рыба"]


async def seed(db: AsyncSession, operator_login: str, operator_password: str) -> None:
    if await db.get(AppSettings, 1) is None:
        db.add(AppSettings(id=1))

    existing = set((await db.execute(select(MealType.name))).scalars().all())
    for i, name in enumerate(DEFAULT_MEAL_TYPES, start=1):
        if name not in existing:
            db.add(MealType(name=name, sort_order=i))

    has_operator = (
        await db.execute(select(User.id).where(User.role == UserRole.operator))
    ).first()
    if has_operator is None:
        db.add(
            User(
                login=operator_login.lower().strip(),
                password_hash=hash_password(operator_password),
                full_name="Оператор",
                role=UserRole.operator,
            )
        )

    await db.flush()


async def main() -> None:
    import os

    login = os.environ.get("SEED_OPERATOR_LOGIN", "operator")
    password = os.environ.get("SEED_OPERATOR_PASSWORD", "changeme")
    async with SessionLocal() as db:
        await seed(db, login, password)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
