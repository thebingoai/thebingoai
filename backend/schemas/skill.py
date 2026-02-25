from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str
    has_prompt_template: bool
    has_code: bool
    parameters_schema: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SkillToggleRequest(BaseModel):
    is_active: bool
