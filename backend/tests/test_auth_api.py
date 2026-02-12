import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database.session import get_db
from backend.database.base import Base

# Create test database
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override the get_db dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency
app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)


def test_register_user():
    """Test user registration."""
    response = client.post(
        "/api/auth/register",
        json={"email": "newuser@example.com", "password": "password123"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "created_at" in data


def test_register_duplicate_email():
    """Test registering with existing email."""
    # First registration
    client.post(
        "/api/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"}
    )

    # Second registration (should fail)
    response = client.post(
        "/api/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"}
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_login_success():
    """Test successful login."""
    # Register user
    client.post(
        "/api/auth/register",
        json={"email": "logintest@example.com", "password": "password123"}
    )

    # Login
    response = client.post(
        "/api/auth/login",
        json={"email": "logintest@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


def test_login_wrong_password():
    """Test login with wrong password."""
    # Register user
    client.post(
        "/api/auth/register",
        json={"email": "wrongpass@example.com", "password": "password123"}
    )

    # Login with wrong password
    response = client.post(
        "/api/auth/login",
        json={"email": "wrongpass@example.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401


def test_get_current_user():
    """Test getting current user with valid token."""
    # Register and login
    client.post(
        "/api/auth/register",
        json={"email": "currentuser@example.com", "password": "password123"}
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "currentuser@example.com", "password": "password123"}
    )
    token = login_response.json()["access_token"]

    # Get current user
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "currentuser@example.com"


def test_protected_route_without_token():
    """Test accessing protected route without token."""
    response = client.get("/api/auth/me")
    assert response.status_code == 403  # Forbidden (no token)


def test_register_short_password():
    """Test registration with password too short."""
    response = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short"}
    )

    assert response.status_code == 422  # Validation error


def test_logout():
    """Test logout endpoint."""
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert "message" in response.json()
