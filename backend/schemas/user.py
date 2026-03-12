from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: str
    org_id: str | None = None
    sso_id: str | None = None
    auth_provider: str = "sso"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
