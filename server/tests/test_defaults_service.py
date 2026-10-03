import pytest
from sqlalchemy import select

from app.models import MealKind, MealType, UserMealDefault, User, UserRole
from app.services import defaults as svc


async def test_get_and_update_defaults(db_session):
    mt = MealType(name="Мясо", sort_order=1)
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([mt, user])
    await db_session.flush()

    d = await svc.get_defaults(db_session, user)
    assert d.meal_type_id is None
    assert d.meals[MealKind.dinner] is False

    await svc.update_defaults(
        db_session, actor_id=user.id, user=user, meal_type_id=mt.id,
        meals={MealKind.breakfast: True, MealKind.lunch: True},
    )
    d2 = await svc.get_defaults(db_session, user)
    assert d2.meal_type_id == mt.id
    assert d2.meals[MealKind.breakfast] is True
    assert d2.meals[MealKind.breakfast] and d2.meals[MealKind.dinner] is False

    rows = (await db_session.execute(
        select(UserMealDefault).where(UserMealDefault.user_id == user.id)
    )).scalars().all()
    assert len(rows) == 4


async def test_invalid_meal_type(db_session):
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add(user)
    await db_session.flush()
    import uuid

    with pytest.raises(svc.MealTypeInvalid):
        await svc.update_defaults(
            db_session, actor_id=user.id, user=user, meal_type_id=uuid.uuid4(),
            meals={MealKind.breakfast: True},
        )
