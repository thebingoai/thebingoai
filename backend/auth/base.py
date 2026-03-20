"""Auth provider abstraction layer — base class and shared models."""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class AuthUser(BaseModel):
    """Normalized user data from any auth provider."""
    id: str
    email: str
    is_active: bool = True
    is_verified: bool = False


class BaseAuthProvider(ABC):
    """Abstract base class for authentication providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'sso', 'supabase')."""

    @abstractmethod
    async def validate_token(self, access_token: str) -> Optional[AuthUser]:
        """Validate token and return user data, or None."""

    @abstractmethod
    async def logout(self, access_token: str, refresh_token: str) -> bool:
        """Logout/invalidate tokens. Returns success."""

    @abstractmethod
    def get_config(self) -> dict:
        """Return frontend-safe config (public keys, URLs)."""
