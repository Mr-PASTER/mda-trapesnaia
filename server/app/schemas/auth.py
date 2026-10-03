from pydantic import BaseModel


class LoginRequest(BaseModel):
    login: str
    password: str
