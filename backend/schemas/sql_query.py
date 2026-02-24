from pydantic import BaseModel, Field
from typing import List, Any


class SqlQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=10000)
    limit: int = Field(default=100, ge=1, le=1000)


class SqlQueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool = False
