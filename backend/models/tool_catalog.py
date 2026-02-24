from sqlalchemy import Column, String, Boolean, Text, Enum, DateTime
from backend.database.base import Base
from datetime import datetime
import enum
import uuid


class ToolCategory(str, enum.Enum):
    DATA = "data"
    DOCUMENT = "document"
    MEMORY = "memory"
    SKILL = "skill"


class ToolCatalog(Base):
    __tablename__ = "tool_catalog"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tool_key = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    # values_callable ensures SQLAlchemy stores/reads enum by value (lowercase) to match migration
    category = Column(
        Enum(ToolCategory, values_callable=lambda objs: [e.value for e in objs], create_type=False),
        nullable=False,
    )
    is_system = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
