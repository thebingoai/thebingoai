from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base, TimestampMixin
import uuid


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    feature_flags = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        default=dict,
    )
