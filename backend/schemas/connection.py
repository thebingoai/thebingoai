from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from backend.models.database_connection import DatabaseType
from datetime import datetime


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    db_type: str
    host: str
    port: int = Field(..., gt=0, lt=65536)
    database: str
    username: str
    password: str
    ssl_enabled: bool = False
    ssl_ca_cert: Optional[str] = None

    @field_validator('db_type')
    @classmethod
    def validate_db_type(cls, v):
        if not DatabaseType.is_valid(v):
            raise ValueError(f"Unsupported database type: {v}")
        return v

    @field_validator('ssl_ca_cert')
    @classmethod
    def validate_ca_cert(cls, v):
        if v is not None and v.strip():
            v = v.strip()
            if not v.startswith('-----BEGIN CERTIFICATE-----'):
                raise ValueError('CA certificate must be in PEM format')
        return v


class ConnectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, lt=65536)
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_enabled: Optional[bool] = None
    ssl_ca_cert: Optional[str] = None  # empty string or null = clear cert
    is_active: Optional[bool] = None
    source_filename: Optional[str] = None

    @field_validator('ssl_ca_cert')
    @classmethod
    def validate_ca_cert(cls, v):
        if v is not None and v.strip():
            v = v.strip()
            if not v.startswith('-----BEGIN CERTIFICATE-----'):
                raise ValueError('CA certificate must be in PEM format')
        return v


class ConnectionResponse(BaseModel):
    id: int
    user_id: str
    name: str
    db_type: str
    host: str
    port: int
    database: str
    username: str
    ssl_enabled: bool
    has_ssl_ca_cert: bool
    is_active: bool
    # schema_json_path removed to prevent filesystem path leakage
    schema_generated_at: Optional[datetime]
    table_count: Optional[int]
    profiling_status: str = "pending"  # pending|in_progress|ready|failed
    profiling_progress: Optional[str] = None
    profiling_error: Optional[str] = None
    source_filename: Optional[str] = None  # Plugin metadata: original uploaded filename
    dataset_table_name: Optional[str] = None  # Plugin metadata: storage key for dataset file
    is_ephemeral: bool = False
    schema_fingerprint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectorTypeResponse(BaseModel):
    id: str
    display_name: str
    description: str
    default_port: int
    badge_variant: str
    version: str | None = None
    card_meta_items: list[str]


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class SchemaRefreshResponse(BaseModel):
    success: bool
    message: str
    schema_generated_at: datetime | None = None


class SchemaResponse(BaseModel):
    connection_id: int
    connection_name: str
    db_type: str
    generated_at: str
    schemas: Dict[str, Any]
    table_names: List[str]
    relationships: List[Dict[str, str]]
