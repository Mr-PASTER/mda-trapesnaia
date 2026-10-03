import pytest

from app.models import MealType
from app.services import meal_types


async def _actor(db_session):
    from app.models import User, UserRole

    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_create_and_list(db_session):
    actor = await _actor(db_session)
    await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Мясо", sort_order=1)
    names = [m.name for m in await meal_types.list_meal_types(db_session)]
    assert names == ["Мясо"]


async def test_cannot_deactivate_last_active(db_session):
    actor = await _actor(db_session)
    m = await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Мясо")
    with pytest.raises(meal_types.LastMealType):
        await meal_types.deactivate_meal_type(db_session, actor_id=actor.id, meal_type_id=m.id)


async def test_deactivate_when_more_than_one(db_session):
    actor = await _actor(db_session)
    a = await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Мясо", sort_order=1)
    await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Пост", sort_order=2)
    await meal_types.deactivate_meal_type(db_session, actor_id=actor.id, meal_type_id=a.id)
    assert [m.name for m in await meal_types.list_meal_types(db_session)] == ["Пост"]
