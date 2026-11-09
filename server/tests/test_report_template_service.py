import pytest

from app.models import Hall, User, UserRole
from app.services import report_template as svc


async def _ctx(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    h1, h2 = Hall(name="Зал №1"), Hall(name="Зал №2")
    db_session.add_all([actor, h1, h2])
    await db_session.flush()
    return actor, h1, h2


def _group(name, hall_ids):
    return svc.TemplateGroup(id=None, name=name, show_subtotal=True, hall_ids=list(hall_ids))


async def test_replace_and_read_back(db_session):
    actor, h1, h2 = await _ctx(db_session)
    await svc.replace_template(
        db_session,
        actor_id=actor.id,
        groups=[_group("Студенты", [h2.id, h1.id])],
        totals=[svc.TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    tpl = await svc.get_template(db_session)
    assert [g.name for g in tpl.groups] == ["Студенты"]
    assert tpl.groups[0].hall_ids == [h2.id, h1.id]
    assert tpl.groups[0].show_subtotal is True
    assert tpl.totals[0].all_halls is True
    assert tpl.totals[0].hall_ids == []


async def test_duplicate_hall_in_group_rejected(db_session):
    actor, h1, _ = await _ctx(db_session)
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id,
            groups=[_group("Студенты", [h1.id, h1.id])], totals=[],
        )


async def test_all_halls_with_list_rejected(db_session):
    actor, h1, _ = await _ctx(db_session)
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id, groups=[],
            totals=[svc.TemplateTotal(
                id=None, name="ИТОГО", all_halls=True, hall_ids=[h1.id]
            )],
        )


async def test_total_without_halls_rejected(db_session):
    actor, _, _ = await _ctx(db_session)
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id, groups=[],
            totals=[svc.TemplateTotal(id=None, name="ИТОГО", all_halls=False, hall_ids=[])],
        )


async def test_inactive_hall_rejected(db_session):
    actor, h1, _ = await _ctx(db_session)
    h1.is_active = False
    await db_session.flush()
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id, groups=[_group("Студенты", [h1.id])], totals=[],
        )


async def test_replace_is_full(db_session):
    actor, h1, h2 = await _ctx(db_session)
    await svc.replace_template(
        db_session, actor_id=actor.id, groups=[_group("A", [h1.id])], totals=[],
    )
    await svc.replace_template(
        db_session, actor_id=actor.id, groups=[_group("B", [h2.id])], totals=[],
    )
    tpl = await svc.get_template(db_session)
    assert [g.name for g in tpl.groups] == ["B"]
