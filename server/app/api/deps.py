from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import User, UserRole
from app.services import auth


async def get_current_user(
    authorization: str = Header(...),
    x_device_fingerprint: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_auth_header")
    raw_token = authorization.removeprefix("Bearer ").strip()
    user = await auth.resolve_session(db, raw_token, x_device_fingerprint)
    # resolve_session мог отозвать сессию (несовпадение отпечатка устройства)
    # через flush, поэтому фиксируем изменения и на пути отказа.
    await db.commit()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_session")
    return user


def require_roles(*roles: UserRole) -> Callable:
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _dep
