# Phase 02: Authentication System

## Objective

Implement JWT-based authentication with bcrypt password hashing, registration, login, and FastAPI security dependencies for protecting endpoints.

## Prerequisites

- Phase 01: App Database (User model must exist)

## Files to Create

### Auth Services
- `backend/auth/__init__.py` - Export auth functions
- `backend/auth/password.py` - Bcrypt hashing and verification
- `backend/auth/jwt.py` - JWT token creation and validation
- `backend/auth/dependencies.py` - FastAPI security dependencies

### Auth API
- `backend/api/auth.py` - Registration, login, token refresh endpoints
- `backend/schemas/auth.py` - Pydantic schemas for auth requests/responses
- `backend/schemas/user.py` - User response schemas

### Tests
- `backend/tests/test_auth.py` - Unit tests for auth functions
- `backend/tests/test_auth_api.py` - Integration tests for auth endpoints

## Files to Modify

- `backend/config.py` - Add JWT secret and expiry settings
- `backend/api/routes.py` - Register auth routes
- `requirements.txt` - Add passlib, bcrypt, python-jose

## Implementation Details

### 1. Configuration (backend/config.py)

Add JWT settings to Settings class:

```python
# JWT Authentication
jwt_secret_key: str = Field(
    default="your-secret-key-change-in-production",
    description="Secret key for JWT token signing"
)
jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
jwt_expiration_minutes: int = Field(default=1440, description="JWT expiration in minutes (24 hours)")
```

### 2. Password Hashing (backend/auth/password.py)

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

### 3. JWT Tokens (backend/auth/jwt.py)

```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from backend.config import settings

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expiration_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
```

### 4. FastAPI Dependencies (backend/auth/dependencies.py)

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.auth.jwt import decode_access_token
from backend.database.session import get_db
from backend.models.user import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    Usage in endpoint:
        @router.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency to ensure user is active.
    (For future use when we add user.is_active field)
    """
    return current_user
```

### 5. Auth Schemas (backend/schemas/auth.py)

```python
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration

class RefreshTokenRequest(BaseModel):
    refresh_token: str
```

### 6. User Schemas (backend/schemas/user.py)

```python
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Enable ORM mode
```

### 7. Auth API (backend/api/auth.py)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.models.user import User
from backend.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from backend.schemas.user import UserResponse
from backend.auth.password import hash_password, verify_password
from backend.auth.jwt import create_access_token
from backend.auth.dependencies import get_current_user
from backend.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user.

    - **email**: Valid email address (must be unique)
    - **password**: Minimum 8 characters
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    hashed = hash_password(request.password)
    user = User(email=request.email, hashed_password=hashed)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login and receive JWT access token.

    - **email**: Registered email address
    - **password**: User password
    """
    # Find user
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Create JWT token
    access_token = create_access_token(data={"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60  # Convert to seconds
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Requires: Bearer token in Authorization header
    """
    return current_user

@router.post("/logout")
async def logout():
    """
    Logout endpoint (client should discard token).

    Note: JWT tokens cannot be invalidated server-side in this implementation.
    Client must discard the token. For production, consider token blacklist.
    """
    return {"message": "Logged out successfully. Please discard your token."}
```

### 8. Register Auth Routes (backend/api/routes.py)

```python
from backend.api import auth  # Add this import

# In create_api_router() function:
api_router.include_router(auth.router)
```

### 9. Update Requirements (requirements.txt)

Add:
```
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
```

## Testing & Verification

### Unit Tests (backend/tests/test_auth.py)

```python
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
```

### Integration Tests (backend/tests/test_auth_api.py)

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.session import get_db
from backend.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test client setup
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
```

### Manual Testing Steps

1. **Start backend**:
   ```bash
   docker-compose up -d
   docker-compose logs -f backend
   ```

2. **Test registration via API docs**:
   - Open http://localhost:8000/docs
   - Navigate to POST /api/auth/register
   - Try it out with:
     ```json
     {
       "email": "admin@example.com",
       "password": "admin12345"
     }
     ```
   - Verify: 201 Created response with user data

3. **Test login**:
   - Navigate to POST /api/auth/login
   - Try it out with registered credentials
   - Verify: Token returned with `access_token` field
   - Copy the access_token value

4. **Test protected endpoint**:
   - Click "Authorize" button at top of docs page
   - Paste token in "Value" field (without "Bearer" prefix)
   - Click "Authorize"
   - Navigate to GET /api/auth/me
   - Try it out
   - Verify: Returns user data

5. **Test invalid token**:
   - Authorize with token "invalid-token-12345"
   - Try GET /api/auth/me
   - Verify: 401 Unauthorized

6. **Run integration tests**:
   ```bash
   pytest backend/tests/test_auth_api.py -v
   ```

## MCP Browser Testing

Use chrome-devtools MCP to verify auth flow in browser (when frontend is built in Phase 9).

For now, test via Swagger UI:

1. **Open Swagger UI**:
   ```python
   from mcp__chrome_devtools import navigate_page, take_snapshot

   navigate_page(url="http://localhost:8000/docs", type="url")
   take_snapshot()
   ```

2. **Verify auth endpoints visible**:
   - POST /api/auth/register
   - POST /api/auth/login
   - GET /api/auth/me
   - POST /api/auth/logout

## Code Review Checklist

- [ ] Passwords never logged or returned in responses
- [ ] Bcrypt used for password hashing (not plain SHA256)
- [ ] JWT secret key loaded from environment (not hardcoded)
- [ ] JWT tokens include expiration time
- [ ] Email validation uses EmailStr from Pydantic
- [ ] Password minimum length enforced (8 characters)
- [ ] User existence checked before registration
- [ ] Constant-time comparison for password verification (handled by bcrypt)
- [ ] 401 errors for both wrong email and wrong password (no user enumeration)
- [ ] Bearer token scheme used (not Basic auth)
- [ ] Dependencies use async def (FastAPI best practice)
- [ ] Database sessions properly closed (via get_db dependency)

## Security Considerations

- [ ] JWT secret must be changed in production (.env file)
- [ ] HTTPS required in production (tokens sent in headers)
- [ ] Token expiration set to reasonable time (24 hours)
- [ ] Consider token refresh mechanism for production
- [ ] Consider token blacklist for logout in production
- [ ] Rate limiting on login endpoint (add in production)
- [ ] CORS configured to allow frontend domain only

## Done Criteria

1. User can register with email and password
2. Registration rejects duplicate emails
3. Registration rejects weak passwords (< 8 chars)
4. User can login and receive JWT token
5. Login fails with wrong password
6. Protected endpoints require valid JWT token
7. GET /api/auth/me returns current user data
8. Invalid tokens rejected with 401
9. All unit tests pass
10. All integration tests pass
11. Swagger UI shows all auth endpoints
12. Code review checklist complete

## Rollback Plan

If this phase fails:
1. Remove backend/auth/ directory
2. Remove backend/schemas/auth.py and backend/schemas/user.py
3. Remove auth routes from backend/api/routes.py
4. Remove passlib and python-jose from requirements.txt
5. Remove JWT settings from backend/config.py
6. Roll back any database changes (users table remains, but no auth logic)
