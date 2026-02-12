from sqlalchemy import Column, String, Integer, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import enum


class DatabaseType(str, enum.Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"


class DatabaseConnection(Base, TimestampMixin):
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)  # User-friendly name
    db_type = Column(Enum(DatabaseType), nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    database = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)  # TODO: Encrypt in Phase 2
    is_active = Column(Boolean, default=True, nullable=False)

    # Schema caching
    schema_json_path = Column(String, nullable=True)
    schema_generated_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="database_connections")
