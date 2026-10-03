from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models import User, UserRole
from app.services import auth


async def get_session_token(request: Request) -> str:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    return token


async def get_current_user(
    token: str = Depends(get_session_token),
    x_device_fingerprint: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await auth.resolve_session(db, token, x_device_fingerprint)
    # resolve_session мог отозвать сессию (несовпадение отпечатка) через flush;
    # коммитим и на пути отказа, иначе отзыв потеряется вместе с rollback.
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
