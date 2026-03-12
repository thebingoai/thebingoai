from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class SSOLogoutRequest(BaseModel):
    refresh_token: str


class SSOConfigResponse(BaseModel):
    sso_base_url: str
    publishable_key: str
    google_oauth_url: str
