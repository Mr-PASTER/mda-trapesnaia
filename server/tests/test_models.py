import uuid

from app.models import MealType, User, UserRole


async def test_create_user_and_meal_type(db_session):
    mt = MealType(name="Мясо", sort_order=1)
    db_session.add(mt)
    await db_session.flush()

    user = User(
        login="ivan",
        password_hash="x",
        full_name="Иван",
        role=UserRole.eater,
        default_meal_type_id=mt.id,
    )
    db_session.add(user)
    await db_session.flush()

    assert isinstance(user.id, uuid.UUID)
    assert user.is_active is True
