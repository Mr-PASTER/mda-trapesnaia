import pytest

from app.services import halls


async def _mk_actor(db_session):
    from app.models import User, UserRole

    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_create_and_list_halls(db_session):
    actor = await _mk_actor(db_session)
    h = await halls.create_hall(db_session, actor_id=actor.id, name="Зал №1")
    assert h.name == "Зал №1"
    assert (await halls.list_halls(db_session))[0].id == h.id


async def test_duplicate_hall_name_raises(db_session):
    actor = await _mk_actor(db_session)
    await halls.create_hall(db_session, actor_id=actor.id, name="Зал №1")
    with pytest.raises(halls.HallAlreadyExists):
        await halls.create_hall(db_session, actor_id=actor.id, name="Зал №1")


async def test_deactivate_hall(db_session):
    actor = await _mk_actor(db_session)
    h = await halls.create_hall(db_session, actor_id=actor.id, name="Зал №2")
    await halls.deactivate_hall(db_session, actor_id=actor.id, hall_id=h.id)
    assert (await halls.list_halls(db_session)) == []
    assert len(await halls.list_halls(db_session, only_active=False)) == 1
