from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class SkillReferenceResponse(BaseModel):
    id: str
    title: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str
    skill_type: str
    has_prompt_template: bool
    has_code: bool
    has_instructions: bool
    reference_count: int
    version: int
    parameters_schema: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SkillDetailResponse(SkillResponse):
    instructions: Optional[str] = None
    prompt_template: Optional[str] = None
    activation_hint: Optional[str] = None
    references: List[SkillReferenceResponse] = []


class SkillToggleRequest(BaseModel):
    is_active: bool


class SkillSuggestionResponse(BaseModel):
    id: str
    suggested_name: str
    suggested_description: Optional[str] = None
    suggested_skill_type: str
    pattern_summary: Optional[str] = None
    confidence: float
    status: str
    recommendation: Optional[str] = None
    recommendation_reason: Optional[str] = None
    frequency_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SkillSuggestionRespondRequest(BaseModel):
    action: str  # "accept" | "dismiss"
