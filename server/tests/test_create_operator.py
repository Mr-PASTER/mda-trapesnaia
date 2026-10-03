import pytest

from app.core.security import verify_password
from app.create_operator import (
    InvalidInput,
    NotOperator,
    PasswordResetRequired,
    ensure_operator,
)
from app.models import User, UserRole


async def test_creates_operator_with_normalized_login(db_session):
    user = await ensure_operator(
        db_session, login="  Root ", full_name="Главный", password="secret"
    )
    assert user.role == UserRole.operator
    assert user.login == "root"
    assert user.is_active is True
    assert verify_password(user.password_hash, "secret")


async def test_duplicate_requires_explicit_reset(db_session):
    await ensure_operator(db_session, login="root", full_name="A", password="secret")
    with pytest.raises(PasswordResetRequired):
        await ensure_operator(db_session, login="root", full_name="A", password="other")

    updated = await ensure_operator(
        db_session, login="root", full_name="B", password="other2", reset_password=True
    )
    assert updated.full_name == "B"
    assert verify_password(updated.password_hash, "other2")


async def test_login_taken_by_non_operator(db_session):
    db_session.add(
        User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    )
    await db_session.flush()
    with pytest.raises(NotOperator):
        await ensure_operator(db_session, login="ivan", full_name="И", password="secret")


async def test_reset_reactivates_inactive_operator(db_session):
    user = await ensure_operator(db_session, login="root", full_name="A", password="secret")
    user.is_active = False
    await db_session.flush()

    again = await ensure_operator(
        db_session, login="root", full_name="A", password="secret", reset_password=True
    )
    assert again.is_active is True


@pytest.mark.parametrize(
    "login,password",
    [("", "secret"), ("root", "1")],
)
async def test_validation_rejects_bad_input(db_session, login, password):
    with pytest.raises(InvalidInput):
        await ensure_operator(db_session, login=login, full_name="A", password=password)
