from sqlalchemy import select

from app.models import AuditLog, User, UserRole
from app.services import audit


async def test_record_writes_audit_log(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(actor)
    await db_session.flush()

    await audit.record(
        db_session,
        actor_id=actor.id,
        action="create",
        entity_type="hall",
        entity_id="abc",
        details={"name": "Зал №1"},
    )
    await db_session.flush()

    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "create"
    assert rows[0].entity_type == "hall"
    assert rows[0].details == {"name": "Зал №1"}
