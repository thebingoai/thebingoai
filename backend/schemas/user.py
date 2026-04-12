from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr


class UserResponse(UserBase):
    id: str
    org_id: str | None = None
    sso_id: str | None = None
    auth_provider: str = "sso"
    created_at: datetime
    updated_at: datetime
    role: Optional[str] = None  # "admin" | "user" | None (when plugin not loaded)

    class Config:
        from_attributes = True
