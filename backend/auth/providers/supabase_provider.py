"""Supabase auth provider — JWT validation for community edition."""

import logging
from typing import Optional

import jwt

from backend.auth.base import AuthUser, BaseAuthProvider
from backend.config import settings

logger = logging.getLogger(__name__)


class SupabaseAuthProvider(BaseAuthProvider):
    """Supabase authentication provider using JWT validation."""

    @property
    def name(self) -> str:
        return "supabase"

    async def validate_token(self, access_token: str) -> Optional[AuthUser]:
        """Decode and validate a Supabase JWT."""
        try:
            payload = jwt.decode(
                access_token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )

            return AuthUser(
                id=payload["sub"],
                email=payload.get("email", ""),
                is_active=True,
                is_verified=payload.get("email_confirmed_at") is not None,
            )
        except jwt.PyJWTError as e:
            logger.debug(f"Supabase JWT validation failed: {e}")
            return None

    async def logout(self, access_token: str, refresh_token: str) -> bool:
        """No-op — Supabase handles session invalidation client-side."""
        return True

    def get_config(self) -> dict:
        """Return Supabase config for the frontend."""
        return {
            "provider": "supabase",
            "supabase_url": settings.supabase_url,
            "supabase_anon_key": settings.supabase_anon_key,
        }
