import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    currency: str = "SAR"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenData(BaseModel):
    user_id: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
