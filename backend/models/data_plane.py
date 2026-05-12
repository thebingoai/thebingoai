import uuid as _uuid

from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base, TimestampMixin


class DataPlaneModel(Base, TimestampMixin):
    __tablename__ = "data_planes"

    id = Column(String, primary_key=True, default=lambda: str(_uuid.uuid4()))
    owner_scope_kind = Column(String(8), nullable=False)   # user | team | org
    owner_scope_id = Column(String, nullable=False)        # matches the respective table's PK
    type = Column(String(32), nullable=False)              # local_filesystem | google_cloud_project
    config = Column(
        JSONB, nullable=False, server_default=text("'{}'"), default=dict,
    )
    credentials_encrypted = Column(String, nullable=True)  # Fernet-encrypted secret JSON
    is_default = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    # Python-side enum: {customer, bingo}. Bingo-managed rows are
    # auto-provisioned in INTERNAL_GCP_PROJECT and cannot be edited/deleted.
    managed_by = Column(
        String(16),
        nullable=False,
        server_default="customer",
        default="customer",
    )
