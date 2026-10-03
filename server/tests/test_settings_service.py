from datetime import time

import pytest

from app.models import User, UserRole
from app.services import settings as svc


async def _actor(db_session):
    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_get_creates_defaults(db_session):
    s = await svc.get_settings(db_session)
    assert s.generation_days == 14
    assert s.deadline_offset_days == 2


async def test_update_settings(db_session):
    actor = await _actor(db_session)
    s = await svc.update_settings(
        db_session,
        actor_id=actor.id,
        generation_days=30,
        deadline_offset_days=3,
        deadline_time=time(12, 30),
    )
    assert s.generation_days == 30
    assert s.deadline_offset_days == 3
    assert s.deadline_time == time(12, 30)


async def test_invalid_values_rejected(db_session):
    actor = await _actor(db_session)
    with pytest.raises(ValueError):
        await svc.update_settings(db_session, actor_id=actor.id, generation_days=0)
    with pytest.raises(ValueError):
        await svc.update_settings(db_session, actor_id=actor.id, deadline_offset_days=-1)
