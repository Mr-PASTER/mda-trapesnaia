from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_bearer_token, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserOut
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    x_device_fingerprint: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    user = await auth.authenticate(db, payload.login, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    token = await auth.create_session(db, user, x_device_fingerprint)
    await db.commit()
    return LoginResponse(token=token, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(get_bearer_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    await auth.revoke_session(db, token)
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
