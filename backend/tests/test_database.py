import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection, DatabaseType
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.agent_step import AgentStep, AgentType, StepType
from backend.models.token_usage import TokenUsage, OperationType


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

    user_id = user.id
    conn_id = conn.id

    # Delete user
    test_db.delete(user)
    test_db.commit()

    # Verify connection was also deleted
    deleted_conn = test_db.query(DatabaseConnection).filter_by(id=conn_id).first()
    assert deleted_conn is None
