"""Per-Organization feature flags (Phase 0 — preflight).

Reader, setter, and `@requires_flag` decorator for behavior gates consumed by
later phases. Flags live in `organizations.feature_flags` (JSONB), cached in
Redis (`org:{id}:feature_flags`, TTL 60s).

Flag registry (kept up-to-date so removed flags don't get re-introduced
silently — see test_feature_flags::test_known_flags):

    new_data_plane               — Phase 1 soft-cutover gate
    new_pipelines                — Phase 2 dispatcher gate
    substrate_migration_complete — Phase 3 fallback removal
    new_dbt                      — Phase 4 dispatcher gate
    governance_v0                — Phase G stage 0
    governance_v1                — Phase G stage 1
    governance_v2                — Phase G stage 2
"""
from __future__ import annotations

import functools
import json
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
_CACHE_KEY_PREFIX = "org"
_CACHE_KEY_SUFFIX = "feature_flags"

KNOWN_FLAGS: frozenset[str] = frozenset({
    "new_data_plane",
    "new_pipelines",
    "substrate_migration_complete",
    "new_dbt",
    "governance_v0",
    "governance_v1",
    "governance_v2",
})


class FlagDisabled:
    """Sentinel returned by @requires_flag when the gating flag is off.

    Distinct from None so callers can disambiguate "flag disabled" from
    "function ran and returned None".
    """

    _instance: "FlagDisabled | None" = None

    def __new__(cls) -> "FlagDisabled":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<FlagDisabled>"

    def __bool__(self) -> bool:
        return False


FLAG_DISABLED = FlagDisabled()

F = TypeVar("F", bound=Callable[..., Any])


def _cache_key(org_id: str) -> str:
    return f"{_CACHE_KEY_PREFIX}:{org_id}:{_CACHE_KEY_SUFFIX}"


def _get_redis():
    """Lazy redis client (sync). Mirrors the pattern in services/query_result_store.py."""
    import redis as syncredis
    from backend.config import settings
    return syncredis.from_url(settings.redis_url, decode_responses=True)


def _load_from_db(org_id: str) -> dict[str, Any]:
    """Fetch organizations.feature_flags for org_id; {} if row missing or JSON malformed."""
    from backend.database.session import SessionLocal
    from backend.models.organization import Organization

    with SessionLocal() as db:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if org is None:
            return {}
        flags = getattr(org, "feature_flags", None)
        if isinstance(flags, dict):
            return flags
        if isinstance(flags, str):
            try:
                parsed = json.loads(flags)
                return parsed if isinstance(parsed, dict) else {}
            except (ValueError, TypeError):
                logger.warning("organizations.feature_flags malformed JSON for org %s; using {}", org_id)
                return {}
        return {}


def _get_org_flags(org_id: str) -> dict[str, Any]:
    """Read org's flag map, with Redis cache-through."""
    key = _cache_key(org_id)
    client = _get_redis()
    try:
        cached = client.get(key)
        if cached is not None:
            try:
                parsed = json.loads(cached)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, TypeError):
                logger.warning("feature_flags cache malformed for %s; refetching", key)

        flags = _load_from_db(org_id)
        try:
            client.setex(key, CACHE_TTL_SECONDS, json.dumps(flags))
        except Exception:
            logger.exception("feature_flags cache write failed for %s; serving uncached", key)
        return flags
    finally:
        client.close()


def enabled(org_id: str, flag: str, default: bool = False) -> bool:
    """Return True iff the flag is set truthy for this Org. Falls back to `default` on miss."""
    val = _get_org_flags(org_id).get(flag, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return bool(val)
    return default


def read_flags(org_id: str) -> dict[str, Any]:
    """Return the full flag map for this Org (cache-through). Empty dict if org missing."""
    return dict(_get_org_flags(org_id))


def set_flag(org_id: str, flag: str, value: Any) -> None:
    """Persist a flag value to Postgres and invalidate the Redis cache entry."""
    from backend.database.session import SessionLocal
    from backend.models.organization import Organization

    with SessionLocal() as db:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if org is None:
            raise LookupError(f"Organization {org_id!r} not found")
        flags = dict(org.feature_flags or {})
        flags[flag] = value
        org.feature_flags = flags
        db.add(org)
        db.commit()

    client = _get_redis()
    try:
        client.delete(_cache_key(org_id))
    finally:
        client.close()


def requires_flag(
    flag: str,
    *,
    default: bool = False,
    disabled_return: Any = FLAG_DISABLED,
    org_id_arg: str = "org_id",
) -> Callable[[F], F]:
    """Short-circuit the wrapped function with `disabled_return` when the flag is off.

    The wrapped function must accept the org id either as a kwarg named `org_id_arg`
    (default `"org_id"`) or as its first positional argument.
    """

    def deco(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if org_id_arg in kwargs:
                org_id = kwargs[org_id_arg]
            elif args:
                org_id = args[0]
            else:
                raise TypeError(
                    f"@requires_flag({flag!r}): cannot resolve {org_id_arg!r} from "
                    f"call args; pass it as a kwarg or first positional"
                )
            if not enabled(str(org_id), flag, default=default):
                return disabled_return
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return deco
