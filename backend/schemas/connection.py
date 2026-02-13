from pydantic import BaseModel, Field
from typing import Optional
from backend.models.database_connection import DatabaseType
from datetime import datetime


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    db_type: DatabaseType
    host: str
    port: int = Field(..., gt=0, lt=65536)
    database: str
    username: str
    password: str


class ConnectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, lt=65536)
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class ConnectionResponse(BaseModel):
    id: int
    user_id: str
    name: str
    db_type: DatabaseType
    host: str
    port: int
    database: str
    username: str
    is_active: bool
    # schema_json_path removed to prevent filesystem path leakage
    schema_generated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class SchemaRefreshResponse(BaseModel):
    success: bool
    message: str
    schema_generated_at: datetime
