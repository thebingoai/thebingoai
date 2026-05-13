from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Any, Optional


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
    org_feature_flags: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
