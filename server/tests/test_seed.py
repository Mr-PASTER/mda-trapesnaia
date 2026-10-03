from sqlalchemy import select

from app.models import AppSettings, MealType, User, UserRole
from app.seed import seed


async def test_seed_is_idempotent(db_session):
    await seed(db_session, operator_login="root", operator_password="rootpass")
    await seed(db_session, operator_login="root", operator_password="rootpass")

    settings = await db_session.get(AppSettings, 1)
    assert settings is not None

    names = (await db_session.execute(select(MealType.name))).scalars().all()
    assert sorted(names) == ["Мясо", "Пост", "Рыба"]

    operators = (
        await db_session.execute(select(User).where(User.role == UserRole.operator))
    ).scalars().all()
    assert len(operators) == 1


async def test_seed_backfills_icons_for_existing_types(db_session):
    # Существующий тип без иконки и произвольный тип, не входящий в дефолты.
    db_session.add(MealType(name="Мясо", sort_order=1))
    db_session.add(MealType(name="Свой", sort_order=2))
    await db_session.flush()

    await seed(db_session, operator_login="root", operator_password="rootpass")

    icons = {
        mt.name: mt.icon
        for mt in (await db_session.execute(select(MealType))).scalars().all()
    }
    assert icons == {
        "Мясо": "meat",
        "Пост": "lent",
        "Рыба": "fish",
        "Свой": None,
    }
