import uuid as _uuid

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.database.base import Base, TimestampMixin
from backend.security.encryption import encrypt_password, decrypt_password


class DatabaseType:
    """Registry of known database types. Plugins extend at runtime via register()."""
    POSTGRES = "postgres"
    MYSQL = "mysql"

    _all: dict[str, str] = {}

    @classmethod
    def register(cls, type_id: str, display_name: str):
        cls._all[type_id] = display_name
        setattr(cls, type_id.upper(), type_id)

    @classmethod
    def is_valid(cls, type_id: str) -> bool:
        return type_id in cls._all


# Register built-in types
DatabaseType.register("postgres", "PostgreSQL")
DatabaseType.register("mysql", "MySQL")


class DatabaseConnection(Base, TimestampMixin):
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False,
                  default=lambda: str(_uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    name = Column(String, nullable=False)  # User-friendly name
    db_type = Column(String(50), nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    database = Column(String, nullable=False)
    username = Column(String, nullable=False)
    _encrypted_password = Column("password", String, nullable=False)  # Encrypted at rest
    ssl_enabled = Column(Boolean, default=False, nullable=False)
    _encrypted_ssl_ca_cert = Column("ssl_ca_cert", String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Schema caching
    schema_json_path = Column(String, nullable=True)
    schema_generated_at = Column(DateTime, nullable=True)
    table_count = Column(Integer, nullable=True)

    # Profiling & data context
    profiling_status = Column(String, default="pending", nullable=False)  # pending|in_progress|ready|failed
    profiling_progress = Column(String, nullable=True)           # e.g. "3/12 tables"
    profiling_error = Column(Text, nullable=True)
    profiling_started_at = Column(DateTime, nullable=True)
    profiling_completed_at = Column(DateTime, nullable=True)
    data_context_path = Column(String, nullable=True)            # path to context JSON file

    # Plugin-specific fields (e.g., dataset connector sets these)
    source_filename = Column(String, nullable=True)
    dataset_table_name = Column(String, nullable=True)

    # Ephemeral dataset tracking
    is_ephemeral = Column(Boolean, default=False, nullable=False)
    schema_fingerprint = Column(String(64), nullable=True)

    # Health monitoring (populated by dataset heartbeat)
    health_status = Column(String, nullable=True)        # healthy|unhealthy
    health_checked_at = Column(DateTime, nullable=True)

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

    @hybrid_property
    def ssl_ca_cert(self):
        """Decrypt SSL CA certificate when accessed."""
        if not self._encrypted_ssl_ca_cert:
            return None
        return decrypt_password(self._encrypted_ssl_ca_cert)

    @ssl_ca_cert.setter
    def ssl_ca_cert(self, pem_content):
        """Encrypt SSL CA certificate when set."""
        if pem_content:
            self._encrypted_ssl_ca_cert = encrypt_password(pem_content)
        else:
            self._encrypted_ssl_ca_cert = None

    @hybrid_property
    def has_ssl_ca_cert(self):
        """Check if SSL CA certificate exists."""
        return self._encrypted_ssl_ca_cert is not None
