from datetime import datetime
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, conlist, field_validator


class Kpi(BaseModel):
    label: str
    value: str  # pre-formatted ("$13,816", "92.4%")
    delta_vs_prev: Optional[str] = None
    delta_direction: Optional[Literal["up", "down", "flat"]] = None


class Section(BaseModel):
    heading: str
    prose: str
    widget_id: Optional[Union[str, int]] = None  # dashboard widget id, e.g. "chart_rolling_30d"

    @field_validator("widget_id", mode="before")
    @classmethod
    def coerce_nullish(cls, v):
        # 0 and "" are treated as "no widget"
        if v == 0 or v == "":
            return None
        return v


class BriefingPayload(BaseModel):
    headline: str = Field(..., min_length=1, max_length=240)
    deck: str = Field(..., min_length=1, max_length=600)
    kpis: List[Kpi] = Field(default_factory=list, max_length=3)
    sections: conlist(Section, min_length=1)  # type: ignore[valid-type]
    key_takeaways: conlist(str, min_length=3, max_length=3)  # type: ignore[valid-type]


class BriefingResponse(BaseModel):
    id: int
    user_id: str
    dashboard_id: int
    dashboard_name: Optional[str] = None
    source: str
    status: str
    payload: Optional[BriefingPayload] = None
    error: Optional[str] = None
    date_range_from: Optional[datetime] = None
    date_range_to: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
