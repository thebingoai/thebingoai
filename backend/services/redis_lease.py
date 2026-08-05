"""Cross-replica single-flight, on Redis rather than Postgres advisory locks.

`pg_advisory_lock` does not work on this deployment. `DATABASE_URL` points at a
**transaction-mode** pooler (DO :25061, Supabase :6543), where the lock attaches
to a *server session* that PgBouncer returns to the pool the moment the
transaction commits — with the lock still on it. The next client handed that
session inherits the lock, and because advisory locks are re-entrant within a
session its own acquire succeeds immediately. Every replica proceeds.

Measured against PgBouncer 1.24.1 in transaction mode: two clients, both landing
on backend pid 65, `pg_try_advisory_lock` returned true for both. Direct to
Postgres the same test correctly blocks the second caller.

`database/session.py` states the same constraint ("the ORM relies on no session
state — no server-side prepared statements, SET vars, or advisory locks").

Callers must be idempotent. Losers skip rather than queue — queueing startup
work across replicas is what caused the 2026-06-24 pile-up — and a slow winner
can outlive the TTL, letting a second holder in.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# Redis was unreachable, so the caller ran unguarded. Distinguishes "nothing to
# release" from "we hold a real lease".
UNGUARDED = "__unguarded__"

# redis-py defaults both of these to None — block until the OS gives up, which
# on a blackholed host (SYN dropped, node wedged) is minutes.
#
# That is load-bearing for `renew_lease`, not a nicety. A holder renewing on a
# timer can only enforce a deadline if the renewal *returns*; an unbounded eval
# parks the whole heartbeat, so the deadline is never evaluated, the lease is
# never declared lost, and the holder finishes work on a resource another
# replica has already taken over. Bounded well under one renewal interval so a
# slow attempt cannot push detection past the key's own expiry.
_SOCKET_BOUNDS = {"socket_connect_timeout": 2, "socket_timeout": 3}

# Release only what we still hold: once the TTL lapses the key belongs to
# whoever took it next, and a blind DEL would evict their lease.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

# Same ownership check, for holders that outlive their TTL. A blind EXPIRE would
# push out whatever key happens to be there — including a *newer* holder's lease,
# on our schedule rather than theirs.
_RENEW_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


def acquire_lease(key: str, ttl: int) -> Optional[str]:
    """Try to become the single flight for *key*.

    Returns an opaque token to the winner (pass it to `release_lease`), or None
    to callers that lost and should skip their work.

    Fails **open**: if Redis is unreachable this returns `UNGUARDED` and the
    caller proceeds without single-flight. Losing the guarantee beats losing the
    work — every current caller is best-effort startup provisioning.
    """
    import redis as syncredis

    from backend.config import settings

    token = uuid.uuid4().hex
    try:
        client = syncredis.from_url(settings.redis_url, decode_responses=True, **_SOCKET_BOUNDS)
        held = client.set(key, token, nx=True, ex=ttl)
    except Exception:
        logger.warning(
            "Lease %s unavailable, running without single-flight", key, exc_info=True,
        )
        return UNGUARDED

    return token if held else None


def renew_lease(key: str, token: Optional[str], ttl: int) -> Optional[bool]:
    """Push *key*'s expiry back out to *ttl*, but only while we still hold it.

    For holders whose work has no upper bound — a chat turn nothing times out —
    where the alternative is a TTL long enough to cover the worst case, which is
    also long enough to wedge the resource after a crash.

    Three outcomes, and the caller must distinguish all three:

    - ``True``  — confirmed still ours.
    - ``False`` — confirmed lost. Someone else owns the key; the caller's work is
      no longer exclusive and should stop rather than finish alongside them.
    - ``None``  — **unknown**. Redis was unreachable *from this process*, which
      says nothing about the key. A partition, a DNS blip or a local socket
      exhaustion leaves every other replica talking to Redis quite happily, free
      to acquire the moment our TTL lapses. Treating this as "still ours" is
      what lets two holders run at once.

    A caller that keeps working through ``None`` must therefore track when it
    last got a ``True`` and give up before ``ttl`` elapses from that point —
    past there the key has expired and anyone may hold it.

    Never raises: an unreachable Redis is reported, not thrown.
    """
    if token is None or token == UNGUARDED:
        return True

    try:
        import redis as syncredis

        from backend.config import settings

        client = syncredis.from_url(settings.redis_url, decode_responses=True, **_SOCKET_BOUNDS)
        return bool(client.eval(_RENEW_LUA, 1, key, token, ttl))
    except Exception:
        logger.warning("Failed to renew lease %s", key, exc_info=True)
        return None


def release_lease(key: str, token: Optional[str], client=None) -> bool:
    """Release *key* if this process still holds it. Safe to call with None or
    `UNGUARDED` — both mean there is nothing of ours to release.

    Returns True only when the compare-and-delete actually removed *our* key.
    Cleanup callers can ignore that; a caller with something conditional on
    still being the owner — announcing the work finished, say — needs it, and
    a GET followed by a DELETE could not answer it atomically.

    `client` reuses a connection the caller already holds. Without one this
    opens its own, which is fine for fire-and-forget cleanup and wasteful on a
    path that is already connected.

    Never raises: the TTL is the real backstop, so a failed release is a log
    line rather than something worth unwinding a caller for.
    """
    if token is None or token == UNGUARDED:
        return False

    try:
        if client is None:
            import redis as syncredis

            from backend.config import settings

            client = syncredis.from_url(settings.redis_url, decode_responses=True, **_SOCKET_BOUNDS)
        return bool(client.eval(_RELEASE_LUA, 1, key, token))
    except Exception:
        logger.warning("Failed to release lease %s", key, exc_info=True)
        return False
