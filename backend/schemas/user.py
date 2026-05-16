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
    role: Optional[str] = None  # "bingo_admin" | "user" | None (when plugin not loaded)
    is_subscriber: bool = False
    # Phase 6 of multi-user-org: per-org role assignment for the caller in
    # their current org. "admin" > "member"; None when no assignment / no org.
    # Frontend uses this to gate the Members + Org Credits settings tabs.
    org_role: Optional[str] = None
    org_feature_flags: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
