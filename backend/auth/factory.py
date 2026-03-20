"""Auth provider factory — registry and instantiation."""

from backend.auth.base import BaseAuthProvider
from backend.config import settings

_providers: dict[str, type[BaseAuthProvider]] = {}


def register_provider(name: str, cls: type[BaseAuthProvider]):
    _providers[name] = cls


def get_auth_provider() -> BaseAuthProvider:
    """Return an instance of the configured auth provider."""
    name = settings.auth_provider
    cls = _providers.get(name)
    if not cls:
        raise ValueError(f"Unknown auth provider '{name}'. Available: {list(_providers.keys())}")
    return cls()


# Auto-register SSO provider
from backend.auth.providers.sso_provider import SSOAuthProvider  # noqa: E402
register_provider("sso", SSOAuthProvider)
