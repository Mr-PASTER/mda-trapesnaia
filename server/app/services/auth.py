from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_fingerprint, hash_token, verify_password
from app.models import User, UserSession
from app.repositories import sessions as sessions_repo
from app.repositories import users as users_repo


async def authenticate(db: AsyncSession, login: str, password: str) -> User | None:
    user = await users_repo.get_by_login(db, login)
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


async def create_session(db: AsyncSession, user: User, fingerprint: str) -> str:
    _, raw = await sessions_repo.create(db, user.id, fingerprint)
    return raw


async def resolve_session(
    db: AsyncSession, raw_token: str, fingerprint: str
) -> User | None:
    token_hash = hash_token(raw_token)
    session = await sessions_repo.get_by_token_hash(db, token_hash)
    if session is None:
        return None

    now = datetime.now(timezone.utc)

    if session.revoked_at is not None or session.expires_at <= now:
        return None

    if session.device_fingerprint_hash != hash_fingerprint(fingerprint):
        session.revoked_at = now
        await db.flush()
        return None

    user = await users_repo.get_by_id(db, session.user_id)
    if user is None or not user.is_active:
        return None

    # скользящее продление + отметка активности
    session.last_seen_at = now
    session.expires_at = now + timedelta(days=settings.session_ttl_days)
    await db.flush()
    return user


async def revoke_session(db: AsyncSession, raw_token: str) -> None:
    session = await sessions_repo.get_by_token_hash(db, hash_token(raw_token))
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        await db.flush()
