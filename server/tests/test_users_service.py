import pytest

from app.models import Hall, MealType, User, UserRole
from app.services import users


async def _ctx(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    db_session.add_all([actor, hall, mt])
    await db_session.flush()
    return actor, hall, mt


async def test_create_eater_requires_exactly_one_hall(db_session):
    actor, hall, mt = await _ctx(db_session)
    with pytest.raises(users.InvalidHalls):
        await users.create_user(
            db_session, actor_id=actor.id, login="ivan", password="p",
            full_name="Иван", role=UserRole.eater, hall_ids=[],
        )
    u = await users.create_user(
        db_session, actor_id=actor.id, login="ivan", password="p",
        full_name="Иван", role=UserRole.eater, hall_ids=[hall.id],
        default_meal_type_id=mt.id,
    )
    assert u.login == "ivan"
    assert await users.repo.hall_ids_of(db_session, u.id) == {hall.id}


async def test_duplicate_login(db_session):
    actor, hall, mt = await _ctx(db_session)
    await users.create_user(
        db_session, actor_id=actor.id, login="ivan", password="p",
        full_name="Иван", role=UserRole.eater, hall_ids=[hall.id],
    )
    with pytest.raises(users.LoginAlreadyExists):
        await users.create_user(
            db_session, actor_id=actor.id, login="IVAN", password="p",
            full_name="Иван 2", role=UserRole.eater, hall_ids=[hall.id],
        )


async def test_set_halls_and_soft_hard_delete(db_session):
    actor, hall, mt = await _ctx(db_session)
    u = await users.create_user(
        db_session, actor_id=actor.id, login="ivan", password="p",
        full_name="Иван", role=UserRole.eater, hall_ids=[hall.id],
    )
    await users.deactivate_user(db_session, actor_id=actor.id, user_id=u.id)
    assert u.is_active is False
    await users.hard_delete_user(db_session, actor_id=actor.id, user_id=u.id)
    assert await users.repo.get_by_id(db_session, u.id) is None
