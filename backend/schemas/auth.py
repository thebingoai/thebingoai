from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class SSOLogoutRequest(BaseModel):
    refresh_token: str
