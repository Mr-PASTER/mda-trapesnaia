import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AppSettings, MealType, User, UserRole

DEFAULT_MEAL_TYPES = [("Мясо", "meat"), ("Пост", "lent"), ("Рыба", "fish")]

MIN_OPERATOR_PASSWORD_LENGTH = 8


async def ensure_reference_data(db: AsyncSession) -> None:
    """Идемпотентно создаёт строку настроек и базовые типы питания."""
    if await db.get(AppSettings, 1) is None:
        db.add(AppSettings(id=1))

    existing = {
        mt.name: mt
        for mt in (await db.execute(select(MealType))).scalars().all()
    }
    for i, (name, icon) in enumerate(DEFAULT_MEAL_TYPES, start=1):
        mt = existing.get(name)
        if mt is None:
            db.add(MealType(name=name, icon=icon, sort_order=i))
        elif mt.icon is None:
            mt.icon = icon

    await db.flush()


async def ensure_first_operator(
    db: AsyncSession, operator_login: str, operator_password: str
) -> bool:
    """Создаёт оператора, только если операторов ещё нет. Возвращает факт создания."""
    has_operator = (
        await db.execute(select(User.id).where(User.role == UserRole.operator))
    ).first()
    if has_operator is not None:
        return False

    db.add(
        User(
            login=operator_login.lower().strip(),
            password_hash=hash_password(operator_password),
            full_name="Оператор",
            role=UserRole.operator,
        )
    )
    await db.flush()
    return True


async def seed(db: AsyncSession, operator_login: str, operator_password: str) -> None:
    await ensure_reference_data(db)
    await ensure_first_operator(db, operator_login, operator_password)


async def main() -> None:
    login = os.environ.get("SEED_OPERATOR_LOGIN", "").strip()
    password = os.environ.get("SEED_OPERATOR_PASSWORD", "")

    async with SessionLocal() as db:
        await ensure_reference_data(db)

        # Оператор создаётся только при явно заданных логине и пароле —
        # никакого пароля по умолчанию (иначе учётка окажется предсказуемой).
        if not login and not password:
            print("seed: справочные данные готовы; оператор не задан")
        elif not login or not password:
            print(
                "seed: нужны обе переменные SEED_OPERATOR_LOGIN и "
                "SEED_OPERATOR_PASSWORD — оператор не создан"
            )
        elif len(password) < MIN_OPERATOR_PASSWORD_LENGTH:
            print(
                f"seed: SEED_OPERATOR_PASSWORD короче "
                f"{MIN_OPERATOR_PASSWORD_LENGTH} символов — оператор не создан. "
                f"Создайте вручную: python -m app.create_operator --login {login}"
            )
        elif await ensure_first_operator(db, login, password):
            print(f"seed: создан оператор '{login.lower()}'")
        else:
            print("seed: оператор уже существует — пропущено")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
