from sqlalchemy import Column, String, Integer, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.database.base import Base, TimestampMixin
from backend.security.encryption import encrypt_password, decrypt_password
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
    _encrypted_password = Column("password", String, nullable=False)  # Encrypted at rest
    is_active = Column(Boolean, default=True, nullable=False)

    # Schema caching
    schema_json_path = Column(String, nullable=True)
    schema_generated_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="database_connections")

    @hybrid_property
    def password(self) -> str:
        """Decrypt password when accessed."""
        return decrypt_password(self._encrypted_password)

    @password.setter
    def password(self, plaintext: str):
        """Encrypt password when set."""
        self._encrypted_password = encrypt_password(plaintext)
