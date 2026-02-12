# Phase 01: App Database Setup

## Objective

Set up PostgreSQL application database with SQLAlchemy ORM, Alembic migrations, and core models for users, database connections, conversations, and token usage.

## Prerequisites

- None (first phase)

## Files to Create

### Database Infrastructure
- `backend/database/__init__.py` - Database session management, base class
- `backend/database/session.py` - SQLAlchemy engine, session factory
- `backend/database/base.py` - Declarative base class

### ORM Models
- `backend/models/__init__.py` - Export all models
- `backend/models/user.py` - User model (id, email, hashed_password, created_at, updated_at)
- `backend/models/database_connection.py` - DatabaseConnection model
- `backend/models/conversation.py` - Conversation model (thread_id, user_id, title, created_at)
- `backend/models/message.py` - Message model (conversation_id, role, content, timestamp)
- `backend/models/agent_step.py` - AgentStep model (message_id, agent_type, step_type, tool_name, content, duration_ms)
- `backend/models/token_usage.py` - TokenUsage model (user_id, operation, tokens, cost, timestamp)

### Alembic Setup
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Migration environment
- `alembic/versions/001_initial_schema.py` - Initial migration

## Files to Modify

- `docker-compose.yml` - Add PostgreSQL service
- `backend/config.py` - Add database URL setting
- `requirements.txt` - Add SQLAlchemy, alembic, psycopg2-binary

## Implementation Details

### 1. Docker Compose (docker-compose.yml)

Add PostgreSQL service:

```yaml
  postgres:
    image: postgres:15-alpine
    container_name: llm-cli-postgres
    environment:
      POSTGRES_DB: llm_cli
      POSTGRES_USER: llm_user
      POSTGRES_PASSWORD: llm_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U llm_user"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

Update backend service to depend on postgres:

```yaml
  backend:
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
```

### 2. Config (backend/config.py)

Add database URL to Settings class:

```python
# Database
database_url: str = Field(
    default="postgresql://llm_user:llm_password@localhost:5432/llm_cli",
    description="PostgreSQL database URL"
)
```

### 3. Database Session (backend/database/session.py)

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10,
    echo=settings.log_level == "DEBUG"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 4. Base Class (backend/database/base.py)

```python
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from sqlalchemy import Column, DateTime

class Base(DeclarativeBase):
    """Base class for all models."""
    pass

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

### 5. User Model (backend/models/user.py)

```python
from sqlalchemy import Column, String, Integer
from backend.database.base import Base, TimestampMixin
import uuid

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)

    # Relationships will be added as we create related models
```

### 6. DatabaseConnection Model (backend/models/database_connection.py)

```python
from sqlalchemy import Column, String, Integer, Boolean, Enum, ForeignKey
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

    # Relationships
    user = relationship("User", back_populates="database_connections")
```

### 7. Conversation Model (backend/models/conversation.py)

```python
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin

class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, unique=True, nullable=False, index=True)  # LangGraph thread ID
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)  # Auto-generated from first message

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
```

### 8. Message Model (backend/models/message.py)

```python
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    agent_steps = relationship("AgentStep", back_populates="message", cascade="all, delete-orphan")
```

### 9. AgentStep Model (backend/models/agent_step.py)

**Purpose**: Store agent execution trace for debugging and frontend display.

```python
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime
import enum


class StepType(str, enum.Enum):
    """Type of agent step."""
    REASONING = "reasoning"        # LLM deciding what to do
    TOOL_CALL = "tool_call"        # Tool invocation (action)
    TOOL_RESULT = "tool_result"    # Tool response (result)
    FINAL_ANSWER = "final_answer"  # Final synthesized answer


class AgentType(str, enum.Enum):
    """Which agent produced the step."""
    ORCHESTRATOR = "orchestrator"
    DATA_AGENT = "data_agent"
    RAG_AGENT = "rag_agent"
    SKILL = "skill"


class AgentStep(Base):
    """
    Individual step in agent execution.

    Captures the full reasoning chain:
    - What the LLM thought (reasoning)
    - What tool it called (tool_call)
    - What result it got (tool_result)
    - Final answer (final_answer)

    Frontend can display this as a collapsible "thinking chain".
    """
    __tablename__ = "agent_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    step_number = Column(Integer, nullable=False)       # Order within the message
    agent_type = Column(Enum(AgentType), nullable=False) # Which agent produced this step
    step_type = Column(Enum(StepType), nullable=False)   # reasoning/tool_call/tool_result/final
    tool_name = Column(String, nullable=True)            # e.g. "data_agent", "execute_query", "enrich_with_history"
    content = Column(JSON, nullable=False)               # Flexible: reasoning text, tool args, results
    duration_ms = Column(Integer, nullable=True)         # How long this step took
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="agent_steps")


# Example content JSON by step_type:
#
# REASONING:
# {
#     "text": "User is asking about data. I should call data_agent.",
#     "decision": "route_to_data_agent"
# }
#
# TOOL_CALL:
# {
#     "tool": "data_agent",
#     "args": {"question": "How many users we have?"}
# }
#
# TOOL_RESULT:
# {
#     "tool": "data_agent",
#     "success": true,
#     "result": {"message": "142 users", "sql_queries": [...], "results": [...]}
# }
#
# FINAL_ANSWER:
# {
#     "text": "We have 142 users. Compared to 2 weeks ago (120 users), that's an 18% increase."
# }
```

### 10. TokenUsage Model (backend/models/token_usage.py)

```python
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime
import enum

class OperationType(str, enum.Enum):
    CHAT = "chat"
    MEMORY_GENERATION = "memory_generation"
    QUERY_GENERATION = "query_generation"
    EMBEDDING = "embedding"

class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    operation = Column(Enum(OperationType), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)  # In USD
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="token_usage")
```

### 10. Update Model Relationships (backend/models/user.py)

Add to User model:

```python
from sqlalchemy.orm import relationship

class User(Base, TimestampMixin):
    # ... existing fields ...

    # Relationships
    database_connections = relationship("DatabaseConnection", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    token_usage = relationship("TokenUsage", back_populates="user", cascade="all, delete-orphan")
```

### 11. Alembic Configuration (alembic.ini)

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://llm_user:llm_password@localhost:5432/llm_cli

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

### 12. Alembic Environment (alembic/env.py)

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from backend.database.base import Base
from backend.config import settings

# Import all models to register them with Base
from backend.models import user, database_connection, conversation, message, agent_step, token_usage

config = context.config
config.set_main_option('sqlalchemy.url', settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

### 13. Initial Migration

Generate with:

```bash
alembic revision --autogenerate -m "Initial schema"
```

Review the generated migration file in `alembic/versions/` and verify it creates all tables correctly.

## Testing & Verification

### Unit Tests (backend/tests/test_database.py)

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection, DatabaseType

@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()

def test_create_user(test_db):
    """Test creating a user."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.created_at is not None

def test_create_database_connection(test_db):
    """Test creating a database connection."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conn = DatabaseConnection(
        user_id=user.id,
        name="Test DB",
        db_type=DatabaseType.POSTGRES,
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass"
    )
    test_db.add(conn)
    test_db.commit()

    assert conn.id is not None
    assert conn.user_id == user.id
    assert conn.is_active is True

def test_user_relationships(test_db):
    """Test user relationships."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conn = DatabaseConnection(
        user_id=user.id,
        name="Test DB",
        db_type=DatabaseType.POSTGRES,
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass"
    )
    test_db.add(conn)
    test_db.commit()

    # Reload user and check relationship
    test_db.refresh(user)
    assert len(user.database_connections) == 1
    assert user.database_connections[0].name == "Test DB"
```

### Manual Testing Steps

1. **Start PostgreSQL container**:
   ```bash
   docker-compose up -d postgres
   docker-compose logs postgres
   ```
   Verify: "database system is ready to accept connections"

2. **Run migrations**:
   ```bash
   alembic upgrade head
   ```
   Verify: All tables created without errors

3. **Check database schema**:
   ```bash
   docker exec -it llm-cli-postgres psql -U llm_user -d llm_cli
   \dt
   \d users
   \d database_connections
   \d conversations
   \d messages
   \d agent_steps
   \d token_usage
   \q
   ```
   Verify: All 6 tables exist with correct columns

4. **Test session factory**:
   ```python
   from backend.database.session import SessionLocal
   from backend.models.user import User

   db = SessionLocal()
   user = User(email="admin@example.com", hashed_password="test")
   db.add(user)
   db.commit()
   print(f"Created user: {user.id}")
   db.close()
   ```

5. **Run unit tests**:
   ```bash
   pytest backend/tests/test_database.py -v
   ```
   Verify: All tests pass

## MCP Browser Testing

N/A - Backend only phase

## Code Review Checklist

- [ ] All models use proper SQLAlchemy types (String, Integer, DateTime, etc.)
- [ ] Foreign keys properly defined with ForeignKey()
- [ ] Relationships use back_populates for bidirectional navigation
- [ ] Cascade delete configured for dependent records
- [ ] Indexes on frequently queried columns (email, thread_id, timestamp)
- [ ] UUIDs used for user IDs (security: non-sequential)
- [ ] TimestampMixin applied to relevant models
- [ ] Enum types used for fixed value sets (DatabaseType, OperationType)
- [ ] Connection string includes pool_pre_ping for reliability
- [ ] Database URL not hardcoded (uses settings)
- [ ] Alembic migrations generate cleanly
- [ ] No raw SQL queries (all via ORM)

## Security Considerations

- [ ] Database password will be encrypted in Phase 2 (add TODO comment)
- [ ] User passwords will be bcrypt hashed in Phase 2
- [ ] Database connection uses connection pooling (protects against exhaustion)
- [ ] UUIDs prevent user enumeration attacks
- [ ] Timestamps use UTC (datetime.utcnow)

## Done Criteria

1. PostgreSQL container starts and is healthy
2. All 6 tables created via Alembic migration (users, database_connections, conversations, messages, agent_steps, token_usage)
3. Models can be imported without errors
4. Unit tests pass for all models
5. Can create, read, update records via ORM
6. Foreign key relationships work correctly
7. Docker Compose starts all services (backend, postgres, redis)
8. No schema validation errors in logs
9. Code review checklist complete
10. All files committed to version control

## Rollback Plan

If this phase fails:
1. `docker-compose down -v` (removes postgres volume)
2. Delete `alembic/versions/*.py` files
3. Remove postgres service from docker-compose.yml
4. Revert backend/config.py changes
5. Remove backend/database/ and backend/models/ directories
