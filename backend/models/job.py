from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobResult(BaseModel):
    file_name: str
    chunks_created: int
    vectors_upserted: int
    namespace: str

class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    file_name: str
    namespace: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    chunks_total: Optional[int] = None
    chunks_processed: Optional[int] = None
    error: Optional[str] = None
    result: Optional[JobResult] = None

    class Config:
        use_enum_values = True

class JobListResponse(BaseModel):
    jobs: list[JobInfo]
    count: int
