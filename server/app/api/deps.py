from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import User, UserRole
from app.services import auth

# Схема безопасности для Swagger UI: даёт кнопку Authorize, куда вставляется
# только токен (без "Bearer ") — префикс добавляется автоматически.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Токен из POST /api/v1/auth/login (без префикса Bearer).",
)


async def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_auth_header")
    return credentials.credentials


async def get_current_user(
    token: str = Depends(get_bearer_token),
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
