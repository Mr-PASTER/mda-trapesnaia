from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_fingerprint, hash_token, new_token
from app.models import UserSession


async def create(db: AsyncSession, user_id, fingerprint: str) -> tuple[UserSession, str]:
    raw = new_token()
    now = datetime.now(timezone.utc)
    session = UserSession(
        user_id=user_id,
        token_hash=hash_token(raw),
        device_fingerprint_hash=hash_fingerprint(fingerprint),
        expires_at=now + timedelta(days=settings.session_ttl_days),
    )
    db.add(session)
    await db.flush()
    return session, raw


async def get_by_token_hash(db: AsyncSession, token_hash: str) -> UserSession | None:
    result = await db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    )
    return result.scalar_one_or_none()
