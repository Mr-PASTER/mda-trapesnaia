import pytest

from app.models import Hall, User, UserHall, UserRole
from app.services import access


async def _mk(db_session, login, role, halls):
    u = User(login=login, password_hash="x", full_name=login, role=role)
    db_session.add(u)
    await db_session.flush()
    for h in halls:
        db_session.add(UserHall(user_id=u.id, hall_id=h.id))
    await db_session.flush()
    return u


async def test_self_allowed(db_session):
    eater = await _mk(db_session, "e1", UserRole.eater, [])
    await access.ensure_can_edit_user(db_session, actor=eater, target=eater)


async def test_admin_of_shared_hall_allowed(db_session):
    h1 = Hall(name="Зал №1")
    db_session.add(h1)
    await db_session.flush()
    admin = await _mk(db_session, "a1", UserRole.admin, [h1])
    eater = await _mk(db_session, "e1", UserRole.eater, [h1])
    await access.ensure_can_edit_user(db_session, actor=admin, target=eater)


async def test_admin_other_hall_denied(db_session):
    h1, h2 = Hall(name="Зал №1"), Hall(name="Зал №2")
    db_session.add_all([h1, h2])
    await db_session.flush()
    admin = await _mk(db_session, "a1", UserRole.admin, [h1])
    eater = await _mk(db_session, "e1", UserRole.eater, [h2])
    with pytest.raises(access.AccessDenied):
        await access.ensure_can_edit_user(db_session, actor=admin, target=eater)


async def test_operator_denied(db_session):
    op = await _mk(db_session, "op", UserRole.operator, [])
    eater = await _mk(db_session, "e1", UserRole.eater, [])
    with pytest.raises(access.AccessDenied):
        await access.ensure_can_edit_user(db_session, actor=op, target=eater)
