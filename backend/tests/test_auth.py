import pytest
from backend.auth.password import hash_password, verify_password
from backend.auth.jwt import create_access_token, decode_access_token


def test_password_hashing():
    """Test password hashing and verification."""
    password = "securepassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_token_creation():
    """Test JWT token creation and decoding."""
    data = {"sub": "user-123", "email": "test@example.com"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["email"] == "test@example.com"
    assert "exp" in payload


def test_jwt_invalid_token():
    """Test decoding invalid JWT token."""
    payload = decode_access_token("invalid.token.here")
    assert payload is None
