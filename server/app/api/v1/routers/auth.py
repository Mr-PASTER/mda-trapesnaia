from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session_token
from app.core.config import settings
from app.db.session import get_db
from app.models import Hall, User, UserHall
from app.schemas.auth import LoginRequest
from app.schemas.user import HallBrief, MeOut
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


async def _me_out(db: AsyncSession, user: User) -> MeOut:
    stmt = (
        select(Hall)
        .join(UserHall, UserHall.hall_id == Hall.id)
        .where(UserHall.user_id == user.id)
        .order_by(Hall.name)
    )
    halls = [HallBrief.model_validate(h) for h in (await db.execute(stmt)).scalars().all()]
    out = MeOut.model_validate(user)
    out.halls = halls
    return out


@router.post("/login", response_model=MeOut)
async def login(
    payload: LoginRequest,
    response: Response,
    x_device_fingerprint: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    user = await auth.authenticate(db, payload.login, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    raw_token = await auth.create_session(db, user, x_device_fingerprint)
    await db.commit()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path=settings.session_cookie_path,
    )
    return await _me_out(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(get_session_token),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    await auth.revoke_session(db, token)
    await db.commit()
    response.delete_cookie(settings.session_cookie_name, path=settings.session_cookie_path)


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    return await _me_out(db, user)
