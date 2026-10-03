import pytest

from app.core.security import hash_password
from app.models import User, UserRole
from app.services import auth


@pytest.fixture
async def eater(db_session):
    user = User(
        login="ivan",
        password_hash=hash_password("secret123"),
        full_name="Иван",
        role=UserRole.eater,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_authenticate_ok_and_bad(db_session, eater):
    assert (await auth.authenticate(db_session, "IVAN", "secret123")).id == eater.id
    assert await auth.authenticate(db_session, "ivan", "wrong") is None
    assert await auth.authenticate(db_session, "nobody", "secret123") is None


async def test_session_roundtrip_and_fingerprint_mismatch(db_session, eater):
    token = await auth.create_session(db_session, eater, "dev-A")
    assert (await auth.resolve_session(db_session, token, "dev-A")).id == eater.id
    # другой отпечаток → сессия аннулируется, доступ закрыт
    assert await auth.resolve_session(db_session, token, "dev-B") is None
    # исходный отпечаток больше не работает (сессия отозвана)
    assert await auth.resolve_session(db_session, token, "dev-A") is None


async def test_revoke_session(db_session, eater):
    token = await auth.create_session(db_session, eater, "dev-A")
    await auth.revoke_session(db_session, token)
    assert await auth.resolve_session(db_session, token, "dev-A") is None
