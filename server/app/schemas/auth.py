from pydantic import BaseModel

from app.schemas.user import UserOut


class LoginRequest(BaseModel):
    login: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut
