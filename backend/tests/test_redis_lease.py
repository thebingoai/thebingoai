"""Cross-replica single-flight must actually exclude, and must fail open.

Replaces `pg_advisory_lock`, which does not hold behind a transaction-mode
pooler: the lock rides a server session PgBouncer returns to the pool at commit,
and the next client handed that session inherits it. Measured against PgBouncer
1.24.1 — two clients on the same backend pid, `pg_try_advisory_lock` true for
both. See backend/services/redis_lease.py.
"""

from unittest.mock import patch

import pytest

from backend.services.redis_lease import (
    UNGUARDED, acquire_lease, release_lease, renew_lease,
)

KEY = "bingo:test:lease"


class _FakeRedis:
    """SET NX EX + the release/renew Lua, against a dict."""

    def __init__(self, initial=None, fail=False):
        self.store = dict(initial or {})
        self.ttls: dict[str, int] = {}
        self.fail = fail
        self.evals: list[tuple] = []

    def set(self, key, value, nx=False, ex=None):
        if self.fail:
            raise ConnectionError("redis down")
        if nx and key in self.store:
            return None
        self.store[key] = value
        self.ttls[key] = ex
        return True

    def eval(self, script, numkeys, key, *argv):
        # Both scripts are owner-checked, and both take the token as ARGV[1];
        # renew passes the new TTL as ARGV[2]. Dispatch on what the script does
        # rather than on argument count, so a rewritten script fails loudly.
        token = argv[0]
        self.evals.append((key, token))
        if self.store.get(key) != token:
            return 0
        if "expire" in script:
            self.ttls[key] = int(argv[1])
        else:
            del self.store[key]
        return 1


def _with(client):
    return patch("redis.from_url", return_value=client)


# ── exclusion ───────────────────────────────────────────────────────────────

def test_only_one_replica_wins():
    r = _FakeRedis()
    with _with(r):
        first = acquire_lease(KEY, 900)
        second = acquire_lease(KEY, 900)

    assert first is not None
    assert second is None, "a second replica must not get the lease"


def test_a_second_replica_wins_once_the_first_releases():
    r = _FakeRedis()
    with _with(r):
        first = acquire_lease(KEY, 900)
        release_lease(KEY, first)
        second = acquire_lease(KEY, 900)

    assert second is not None
    assert second != first


def test_lease_carries_a_ttl_so_a_dead_winner_cannot_wedge_it():
    """The whole failure mode advisory locks had: a holder that goes away
    without releasing must not block every future boot."""
    seen = {}

    class _Recording(_FakeRedis):
        def set(self, key, value, nx=False, ex=None):
            seen["ex"] = ex
            return super().set(key, value, nx=nx, ex=ex)

    with _with(_Recording()):
        acquire_lease(KEY, 900)

    assert seen["ex"] == 900


# ── release is owner-checked ────────────────────────────────────────────────

def test_release_only_removes_our_own_lease():
    """Once the TTL lapses the key belongs to whoever took it next — a blind
    DEL would evict their lease."""
    r = _FakeRedis({KEY: "someone-elses-token"})
    with _with(r):
        release_lease(KEY, "our-stale-token")

    assert r.store[KEY] == "someone-elses-token"


def test_release_is_a_noop_for_a_loser():
    r = _FakeRedis({KEY: "winner"})
    with _with(r):
        release_lease(KEY, None)

    assert r.store[KEY] == "winner"
    assert r.evals == [], "a loser must not even talk to redis"


# ── renew is owner-checked too ──────────────────────────────────────────────

def test_renew_extends_our_own_lease():
    """Nothing bounds a chat turn, so one can outrun its TTL. Renewing keeps the
    thread locked for as long as the turn it is guarding actually runs."""
    r = _FakeRedis()
    with _with(r):
        token = acquire_lease(KEY, 600)
        renew_lease(KEY, token, 600)

    assert r.store[KEY] == token
    assert r.ttls[KEY] == 600


def test_renew_does_not_extend_someone_elses_lease():
    """The bug a blind EXPIRE would reintroduce: our lease lapsed, a newer turn
    claimed the key, and we keep pushing *their* expiry out on our schedule."""
    r = _FakeRedis({KEY: "a-newer-turns-token"})
    r.ttls[KEY] = 60
    with _with(r):
        renew_lease(KEY, "our-stale-token", 600)

    assert r.ttls[KEY] == 60, "renewed a lease we no longer hold"


def test_renew_is_a_noop_without_a_real_token():
    r = _FakeRedis()
    with _with(r):
        renew_lease(KEY, None, 600)
        renew_lease(KEY, UNGUARDED, 600)

    assert r.evals == []


def test_renew_never_raises_when_redis_dies():
    class _DiesOnEval(_FakeRedis):
        def eval(self, *a):
            raise ConnectionError("redis down")

    with _with(_DiesOnEval()):
        renew_lease(KEY, "tok", 600)  # the TTL is still the backstop


# ── fails open ──────────────────────────────────────────────────────────────

def test_unreachable_redis_lets_the_caller_proceed():
    """Losing single-flight beats losing the work — every caller is best-effort
    startup provisioning that is idempotent anyway."""
    with _with(_FakeRedis(fail=True)):
        token = acquire_lease(KEY, 900)

    assert token == UNGUARDED


def test_releasing_an_unguarded_run_touches_nothing():
    r = _FakeRedis()
    with _with(r):
        release_lease(KEY, UNGUARDED)

    assert r.evals == []


def test_release_never_raises_when_redis_dies_mid_flight():
    class _DiesOnEval(_FakeRedis):
        def eval(self, *a):
            raise ConnectionError("redis down")

    with _with(_DiesOnEval()):
        release_lease(KEY, "tok")  # must not raise — the TTL is the backstop
