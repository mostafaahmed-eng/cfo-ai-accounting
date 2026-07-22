from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.enums import Language, UserStatus


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    language: Language
    timezone: str
    status: UserStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = None
    language: Language | None = None
    timezone: str | None = None
