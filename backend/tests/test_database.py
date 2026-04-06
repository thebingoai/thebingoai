import pytest
from sqlalchemy import create_engine, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection, DatabaseType
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.agent_step import AgentStep, AgentType, StepType
from backend.models.token_usage import TokenUsage, OperationType
from backend.security.encryption import encrypt_password


def _make_connection(user_id, name="Test DB", **kwargs):
    """Helper to create a DatabaseConnection with an encrypted password."""
    defaults = dict(
        user_id=user_id,
        name=name,
        db_type=DatabaseType.POSTGRES,
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        _encrypted_password=encrypt_password("testpass"),
    )
    defaults.update(kwargs)
    return DatabaseConnection(**defaults)


@pytest.fixture
def test_db():
    """Create test database with SQLite (JSONB columns mapped to JSON)."""
    engine = create_engine("sqlite:///:memory:")

    # Patch JSONB columns to use JSON for SQLite
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()

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

    conn = _make_connection(user.id)
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

    conn = _make_connection(user.id)
    test_db.add(conn)
    test_db.commit()

    # Reload user and check relationship
    test_db.refresh(user)
    assert len(user.database_connections) == 1
    assert user.database_connections[0].name == "Test DB"


def test_create_conversation_and_messages(test_db):
    """Test creating conversations and messages."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conversation = Conversation(
        thread_id="thread-123",
        user_id=user.id,
        title="Test Conversation"
    )
    test_db.add(conversation)
    test_db.commit()

    message = Message(
        conversation_id=conversation.id,
        role="user",
        content="Hello, this is a test message"
    )
    test_db.add(message)
    test_db.commit()

    # Verify
    test_db.refresh(conversation)
    assert len(conversation.messages) == 1
    assert conversation.messages[0].content == "Hello, this is a test message"


def test_create_agent_steps(test_db):
    """Test creating agent steps."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conversation = Conversation(
        thread_id="thread-123",
        user_id=user.id,
        title="Test Conversation"
    )
    test_db.add(conversation)
    test_db.commit()

    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="Here is the response"
    )
    test_db.add(message)
    test_db.commit()

    step = AgentStep(
        message_id=message.id,
        step_number=1,
        agent_type=AgentType.ORCHESTRATOR,
        step_type=StepType.REASONING,
        content={"text": "Analyzing the question", "decision": "route_to_data_agent"}
    )
    test_db.add(step)
    test_db.commit()

    # Verify
    test_db.refresh(message)
    assert len(message.agent_steps) == 1
    assert message.agent_steps[0].agent_type == AgentType.ORCHESTRATOR
    assert message.agent_steps[0].step_type == StepType.REASONING


def test_create_token_usage(test_db):
    """Test creating token usage records."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    usage = TokenUsage(
        user_id=user.id,
        operation=OperationType.CHAT,
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.002
    )
    test_db.add(usage)
    test_db.commit()

    # Verify
    assert usage.id is not None
    assert usage.user_id == user.id
    assert usage.total_tokens == 150


def test_cascade_delete(test_db):
    """Test cascade delete behavior."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conn = _make_connection(user.id)
    test_db.add(conn)
    test_db.commit()

    user_id = user.id
    conn_id = conn.id

    # Delete user
    test_db.delete(user)
    test_db.commit()

    # Verify connection was also deleted
    deleted_conn = test_db.query(DatabaseConnection).filter_by(id=conn_id).first()
    assert deleted_conn is None


def test_ephemeral_connection_fields(test_db):
    """Test creating a connection with ephemeral fields."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conn = _make_connection(
        user.id,
        name="Ephemeral Dataset",
        is_ephemeral=True,
        schema_fingerprint="abc123"
    )
    test_db.add(conn)
    test_db.commit()

    queried = test_db.query(DatabaseConnection).filter_by(id=conn.id).first()
    assert queried.is_ephemeral is True
    assert queried.schema_fingerprint == "abc123"


def test_ephemeral_default_false(test_db):
    """Test that is_ephemeral defaults to False."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conn = _make_connection(user.id, name="Normal Connection")
    test_db.add(conn)
    test_db.commit()

    assert conn.is_ephemeral is False


def test_ephemeral_filter_excludes_ephemeral(test_db):
    """Test that filtering by is_ephemeral==False excludes ephemeral records."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    normal = _make_connection(user.id, name="Normal")
    ephemeral = _make_connection(user.id, name="Ephemeral", is_ephemeral=True)
    test_db.add_all([normal, ephemeral])
    test_db.commit()

    visible = test_db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user.id,
        DatabaseConnection.is_ephemeral == False,  # noqa: E712
    ).all()
    assert len(visible) == 1
    assert visible[0].name == "Normal"


def test_no_filter_includes_all(test_db):
    """Test that querying without ephemeral filter includes both types."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    normal = _make_connection(user.id, name="Normal")
    ephemeral = _make_connection(user.id, name="Ephemeral", is_ephemeral=True)
    test_db.add_all([normal, ephemeral])
    test_db.commit()

    all_conns = test_db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user.id,
    ).all()
    assert len(all_conns) == 2


def test_promote_ephemeral_to_visible(test_db):
    """Test that promoting an ephemeral connection makes it visible in filtered queries."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    conn = _make_connection(user.id, name="Chat Dataset", is_ephemeral=True, db_type="dataset")
    test_db.add(conn)
    test_db.commit()

    # Before promotion: not visible in filtered query
    visible = test_db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user.id,
        DatabaseConnection.is_ephemeral == False,  # noqa: E712
    ).all()
    assert len(visible) == 0

    # Promote
    conn.is_ephemeral = False
    test_db.commit()

    # After promotion: visible
    visible = test_db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user.id,
        DatabaseConnection.is_ephemeral == False,  # noqa: E712
    ).all()
    assert len(visible) == 1
    assert visible[0].name == "Chat Dataset"


def test_promotion_only_affects_datasets(test_db):
    """Test that promotion logic targets dataset-type connections only."""
    user = User(email="test@example.com", hashed_password="hashed123")
    test_db.add(user)
    test_db.commit()

    # A dataset connection (eligible for promotion)
    dataset = _make_connection(user.id, name="Dataset", db_type="dataset", is_ephemeral=True)
    # A regular postgres connection (should never be ephemeral, but test the filter)
    regular = _make_connection(user.id, name="Regular", db_type="postgres")
    test_db.add_all([dataset, regular])
    test_db.commit()

    # Query for ephemeral datasets specifically
    ephemeral_datasets = test_db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user.id,
        DatabaseConnection.db_type == "dataset",
        DatabaseConnection.is_ephemeral == True,  # noqa: E712
    ).all()
    assert len(ephemeral_datasets) == 1
    assert ephemeral_datasets[0].name == "Dataset"


def test_connection_response_ephemeral_fields():
    """Test that ConnectionResponse includes ephemeral fields."""
    from backend.schemas.connection import ConnectionResponse
    from datetime import datetime

    data = {
        "id": 1,
        "user_id": "user-1",
        "name": "Test",
        "db_type": "postgres",
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "username": "testuser",
        "ssl_enabled": False,
        "has_ssl_ca_cert": False,
        "is_active": True,
        "schema_generated_at": None,
        "table_count": None,
        "profiling_status": "pending",
        "profiling_progress": None,
        "profiling_error": None,
        "source_filename": None,
        "dataset_table_name": None,
        "is_ephemeral": True,
        "schema_fingerprint": "fingerprint123",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    response = ConnectionResponse(**data)
    assert response.is_ephemeral is True
    assert response.schema_fingerprint == "fingerprint123"
